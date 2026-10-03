from typing import Dict
from urllib.parse import quote

import httpx2
from domain.cache import CacheKey
from framework.clients.cache_client import CacheClientAsync
from framework.di.service_provider import ServiceProvider
from framework.exceptions.nulls import ArgumentNullException
from framework.logger.providers import get_logger
from framework.uri.uri import Uri
from httpx2 import AsyncClient, Timeout
from quart import Response, request
from services.service_map import ServiceMap
from utilities.utils import fire_task

logger = get_logger(__name__)

IDEMPOTENT_METHODS = frozenset({'GET', 'HEAD', 'PUT', 'DELETE', 'OPTIONS'})

# Connection-scoped headers that belong to the hop, not the message.  Passing
# them through a proxy is wrong in both directions: `transfer-encoding` and
# `content-length` describe a framing that we are re-doing ourselves, and
# `connection` / `upgrade` describe a socket that ends at the gateway.
HOP_BY_HOP_HEADERS = frozenset({
    'connection',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailer',
    'transfer-encoding',
    'upgrade',
})


class ProxyHandler:
    def __init__(
        self,
        service_provider: ServiceProvider,
        service_map: ServiceMap
    ):
        self._provider = service_provider

        self._service_map = service_map
        self._configuration = service_map.service_configuration

        self._cache_client = service_provider.resolve(
            CacheClientAsync)

    def _parse_interpolated_segments(
        self,
        url: str,
        segments: dict
    ) -> str:

        ArgumentNullException.if_none_or_whitespace(url, 'url')
        ArgumentNullException.if_none(segments, 'segments')

        interp_url = url
        for segment in segments:
            repl = f'<{segment}>'
            # Segment values arrive URL-decoded from Werkzeug, so they are
            # percent-encoded again on the way out.  Without this a value
            # containing '?', '#' or '&' is not data any more -- it becomes
            # syntax in the upstream URL.
            interp_url = interp_url.replace(
                repl,
                quote(str(segments[segment]), safe=''))

        return interp_url

    def _build_url(
        self,
        url: str,
        segments: dict
    ) -> str:

        ArgumentNullException.if_none_or_whitespace(url, 'url')

        # Route segments are interpolated into the path *before* the query
        # string is attached.  Substituting into the finished URL would let a
        # segment inject its own query parameters ahead of ours, or truncate
        # the URL at a '#'.
        if any(segments):
            url = self._parse_interpolated_segments(
                url=url,
                segments=segments)

        route_uri = Uri(
            url=f'{self._service_map.base_url}{url}')

        # Handle query params.  Passed as pairs rather than a dict: the
        # inbound args are a MultiDict, and flattening it silently dropped
        # every value but the first of a repeated key (`?tag=a&tag=b`).
        if request.args:
            logger.info(f'Query params: {request.args}')
            route_uri.query = list(request.args.items(multi=True))

        # Handle non-standard port mapping
        if (self._configuration.port
                and self._configuration.port != 0):
            route_uri.port = self._configuration.port

        # Build the proxy endpoint
        proxy_url = route_uri.get_url()

        logger.info(f'Proxy: {proxy_url}')

        return proxy_url

    async def _send_request(
        self,
        url: str
    ):
        logger.info(f'Handling request: {request.method}: {url}')
        logger.info(f'Remote: {request.remote_addr}')
        logger.info(f'Service endpoint: {url}')

        client = self._provider.resolve(
            AsyncClient)

        data = await request.get_data()
        logger.info(f'Content bytes: {len(data)}')

        headers = self._upstream_request_headers()

        try:
            response = await client.request(
                method=request.method,
                url=url,
                content=data,
                headers=headers)
        except httpx2.RemoteProtocolError as ex:
            # The server closed a stale keep-alive connection before the
            # request was transmitted.  Safe to retry once for idempotent
            # methods because the upstream never processed the request.
            if request.method.upper() in IDEMPOTENT_METHODS:
                logger.warning(
                    f'Stale keep-alive, retrying '
                    f'[{request.method} {url}]: {ex}')
                response = await client.request(
                    method=request.method,
                    url=url,
                    content=data,
                    headers=headers)
            else:
                raise

        logger.info(f'Request: {response.request.method}: {response.request.url}: {response.status_code}')

        return response

    def _is_streaming(
        self,
        ingress_route: str
    ) -> bool:
        '''
        Whether this route forwards the upstream response as it arrives.

        Route-level `streaming` wins; otherwise the service-wide default
        applies.  Both default to off, so a mapping that says nothing keeps the
        original buffered behaviour.
        '''

        route_map = self._service_map[ingress_route]

        if route_map.streaming is not None:
            return bool(route_map.streaming)

        return self._configuration.streaming

    def _stream_timeout(
        self,
        ingress_route: str
    ) -> Timeout:
        '''
        Timeout for a streaming request.

        The read timeout is the one that matters: a server-sent-event response
        is idle between events, and the client-wide 120s read timeout would
        tear it down mid-stream.  `None` disables it, which is the right
        default for a stream whose length is the length of the work upstream.
        '''

        route_map = self._service_map[ingress_route]

        read_timeout = route_map.stream_read_timeout
        if read_timeout is None:
            read_timeout = self._configuration.stream_read_timeout

        return Timeout(connect=5.0, read=read_timeout, write=10.0, pool=5.0)

    def _upstream_request_headers(self) -> Dict:
        '''
        Inbound headers to forward upstream, buffered or streaming alike.

        Client-supplied `X-Forwarded-For` is overwritten rather than appended
        to: an upstream that uses it for allowlisting, rate limiting or audit
        logging must not be handed a value the caller chose.

        `Host` is dropped so httpx derives it from the target URL -- the
        upstream sees its own hostname, which is what a service doing Host
        validation expects.  The original is preserved in `X-Forwarded-Host`.
        `Content-Length` is dropped because httpx recalculates it from the body
        we hand it.
        '''

        # The `x-forwarded-*` set is dropped unconditionally rather than just
        # overwritten below: if `remote_addr` were ever unset, an overwrite
        # guarded on it would leave the caller's own value in place, which is
        # exactly the header an upstream must not be able to be lied to about.
        skip = HOP_BY_HOP_HEADERS | {
            'host',
            'content-length',
            'x-forwarded-for',
            'x-forwarded-host',
            'x-forwarded-proto',
        }

        headers = {
            key: value for key, value in request.headers.items()
            if key.lower() not in skip
        }

        if inbound_host := request.headers.get('Host'):
            headers['X-Forwarded-Host'] = inbound_host
        if request.remote_addr:
            headers['X-Forwarded-For'] = request.remote_addr
        headers['X-Forwarded-Proto'] = request.scheme

        return headers

    def _upstream_response_headers(
        self,
        service_response
    ) -> Dict:
        '''
        Upstream response headers to return to the caller, buffered or
        streaming alike.

        Framing headers are stripped: the body is re-chunked by the ASGI server
        as it streams, so an upstream `Content-Length` would contradict what we
        actually send.  `Date` and `Server` are stripped for the same reason --
        our own ASGI server emits them, and forwarding the upstream's produces
        a comma-joined duplicate.
        '''

        skip = HOP_BY_HOP_HEADERS | {'content-length', 'date', 'server'}

        return {
            key: value for key, value in service_response.headers.items()
            if key.lower() not in skip
        }

    async def _stream_request(
        self,
        url: str,
        ingress_route: str
    ) -> Response:
        '''
        Proxy a response without buffering it.

        `send(stream=True)` returns once the status line and headers have
        arrived, leaving the body unread, so the caller starts receiving data
        while the upstream is still producing it.  That is what Streamable HTTP
        and any other server-sent-event endpoint requires: buffering would hold
        every frame until the upstream call finished.

        The request body is still read in full first.  Streaming it too would
        mean handling `Expect: 100-continue` and non-idempotent retries, and
        nothing routed here sends a large request.
        '''

        logger.info(f'Streaming request: {request.method}: {url}')

        client = self._provider.resolve(AsyncClient)
        data = await request.get_data()

        proxy_request = client.build_request(
            method=request.method,
            url=url,
            content=data or None,
            headers=self._upstream_request_headers(),
            timeout=self._stream_timeout(ingress_route))

        service_response = await client.send(proxy_request, stream=True)

        logger.info(
            f'Stream open: {request.method}: {url}: {service_response.status_code}')

        async def body():
            try:
                async for chunk in service_response.aiter_raw():
                    yield chunk
            except Exception as ex:
                # The response head is already on the wire, so this cannot be
                # turned into a 5xx.  Log it and end the stream; the client
                # sees a truncated body, which is the honest outcome.
                logger.warning(
                    f'Stream interrupted [{request.method} {url}]: {ex}')
            finally:
                await service_response.aclose()

        return Response(
            body(),
            status=service_response.status_code,
            headers=self._upstream_response_headers(service_response))

    async def _get_cache(
        self,
        hash_key: str
    ) -> str:
        ArgumentNullException.if_none_or_whitespace(hash_key, 'hash_key')

        try:
            cached_route = await self._cache_client.get_cache(
                key=hash_key)
            return cached_route
        except Exception as ex:
            logger.warning(f'Failed to get cache: {ex}')

    async def _set_cache(
        self,
        hash_key: str,
        service_route: str
    ) -> str:
        ArgumentNullException.if_none_or_whitespace(hash_key, 'hash_key')
        ArgumentNullException.if_none_or_whitespace(
            service_route, 'service_route')

        try:
            await self._cache_client.set_cache(
                key=hash_key,
                value=service_route,
                ttl=60 * 24)
        except Exception as ex:
            logger.warning(f'Failed to get cache: {ex}')

    def _get_segments_from_kwargs(
        self,
        kwargs: Dict
    ):
        return {
            k: v for k, v in kwargs.items()
            if k != 'container'
        }

    async def _get_service_route(
        self,
        ingress_route: str
    ):
        # Create cache key for ingress route
        cache_key = CacheKey.mapped_route(
            service_name=self._service_map.service_name,
            ingress_path=ingress_route)

        logger.info(f'Route cache key: {cache_key}')

        cached_route = await self._get_cache(
            hash_key=cache_key)

        if cached_route is not None:
            logger.info(f'Using cached route: {cached_route}')
            return cached_route

        # Get the route mapping definition
        route_mapping = self._service_map[ingress_route]
        logger.info(f'Service: {route_mapping.service_endpoint}')

        # Fire and forget the write to cache
        fire_task(
            self._set_cache(
                hash_key=cache_key,
                service_route=route_mapping.service_endpoint))

        return route_mapping.service_endpoint

    async def handle_request(
        self,
        **kwargs
    ):
        # Get the inbound request rule
        ingress_route = request.url_rule.rule
        logger.info(f'Ingress route: {ingress_route}')

        service_route = await self._get_service_route(
            ingress_route=ingress_route)

        logger.info(f'Service route: {service_route}')

        service_url = self._build_url(
            url=service_route,
            segments=self._get_segments_from_kwargs(
                kwargs=kwargs
            ))

        logger.info(f'Service URL: {service_url}')

        if self._is_streaming(ingress_route):
            return await self._stream_request(
                url=service_url,
                ingress_route=ingress_route)

        service_response = await self._send_request(
            url=service_url)

        gateway_response = Response(
            response=service_response.content,
            status=service_response.status_code,
            headers=self._upstream_response_headers(service_response))

        # `elapsed` is a property that raises unless httpx timed a real
        # transport round trip, so it cannot be read with a getattr default.
        # Unguarded, this logging statement turned a perfectly good upstream
        # response into a 500.
        try:
            elapsed = service_response.elapsed
        except RuntimeError:
            elapsed = None

        logger.info(
            f'Response: {gateway_response.status_code}: {elapsed}')

        return gateway_response

    async def proxy(
        self,
        **kwargs
    ):
        '''
        Map the proxy route from configuration and inbound request, cache the
        route if it's not already stored and pass the request through to the
        proxy service

        Ingress route: Werkzeug will map the inbound request to a 'rule', this
        lives at request.url_rule.rule.  It's the 'gateway_endpoint' in config

        Hash key: The hash key is calculated from the mapped service route, this
        is not the actual path, as it won't contain any query parameters that are
        passed on the ingress URL.  The mapped endpoint from cache is used to
        build the URL that gets passed into the service, this is where the query
        params are parsed and appended
        '''

        logger.info(f'{request.method}: {request.url_rule}')

        try:
            return await self.handle_request(**kwargs)
        except httpx2.PoolTimeout as ex:
            logger.error(
                f'Pool timeout [{request.method} {request.url}]: {ex}')
            return {'error': 'Gateway timeout'}, 504
        except httpx2.ConnectTimeout as ex:
            logger.error(
                f'Connect timeout [{request.method} {request.url}]: {ex}')
            return {'error': 'Gateway timeout'}, 504
        except httpx2.ReadTimeout as ex:
            logger.error(
                f'Read timeout [{request.method} {request.url}]: {ex}')
            return {'error': 'Gateway timeout'}, 504
        except httpx2.RemoteProtocolError as ex:
            logger.error(
                f'Remote protocol error [{request.method} {request.url}]: {ex}')
            return {'error': 'Bad gateway'}, 502
        except Exception as ex:
            logger.exception(f'Unhandled proxy error [{request.method} {request.url}]: {ex}')
            return {'error': 'Internal server error'}, 500
