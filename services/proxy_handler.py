import traceback

import httpx
from framework.clients.cache_client import CacheClientAsync
from framework.clients.http_client import HttpClient
from framework.crypto.hashing import md5
from framework.logger.providers import get_logger
from framework.uri.uri import Uri
from framework.validators.nulls import not_none
from quart import Response, make_response, request

from services.route_map import RouteMap
from services.service_map import ServiceMap

logger = get_logger(__name__)


class ProxyHandler:
    def __init__(self, container, service: ServiceMap):
        self.service = service
        self.configuration = service.service_configuration

        self.cache_client: CacheClientAsync = container.resolve(
            CacheClientAsync)
        self.http_client = HttpClient()

    def _get_rule(self):
        rule = request.url_rule.rule
        if not rule:
            raise Exception('No Werkzeug mapped rule')
        return rule

    def _parse_interpolated_segments(self, url: str, segments: dict):
        interp_url = url
        for segment in segments:
            repl = f'<{segment}>'
            interp_url = interp_url.replace(
                repl,
                segments[segment])
        return interp_url

    def _build_url(self, url: str, segments: dict) -> str:
        not_none(url, 'url')

        _url = Uri(
            url=f'{self.service.base_url}{url}')

        if request.args:
            _url.query = dict(request.args)

        if (self.configuration.port
                and self.configuration.port != 0):
            _url.port = self.configuration.port

        proxy_url = _url.get_url()
        if any(segments):
            proxy_url = self._parse_interpolated_segments(
                url=proxy_url,
                segments=segments)

        return proxy_url

    async def make_request(self, url: str):
        data = await request.get_data()

        if data:
            response = await self.http_client.request(
                method=request.method,
                url=url,
                data=data,
                headers=request.headers,
                timeout=None)
        else:
            response = await self.http_client.request(
                method=request.method,
                url=url,
                headers=request.headers,
                timeout=None)

        logger.info(
            f'Request: {response.request.method}: {response.request.url}')

        logger.info(f'Service: {response.status_code}')
        logger.info(f'Service: {response.elapsed} elapsed')
        return response

    def _request_hash_key(self, ingress_path: str, kwargs):
        ''' Ingress path being the gateway route /api/{service}/route/details '''

        return md5(f'{ingress_path}{kwargs}')

    async def _get_cache(self, hash_key: str) -> str:
        cached_route = await self.cache_client.get_cache(
            key=hash_key)
        return cached_route

    async def _set_cache(self, hash_key: str, service_route: str) -> str:
        await self.cache_client.set_cache(
            key=hash_key,
            value=service_route,
            ttl=60 * 24)

    def _get_segments(self, kwargs):
        return {
            k: v for k, v in kwargs.items()
            if k != 'container'
        }

    async def handle_request(self, **kwargs):
        ingress_route = self._get_rule()

        hash_key = self._request_hash_key(
            ingress_path=ingress_route,
            kwargs=kwargs)

        cached_route = await self._get_cache(
            hash_key=hash_key)

        if not cached_route:
            logger.info('No cached endpoint, fetching from route map')

            route: RouteMap = self.service[ingress_route]
            service_route = route.service_endpoint

            await self._set_cache(
                hash_key=hash_key,
                service_route=route.service_endpoint)
        else:
            service_route = cached_route
            logger.info('Endpoint returned from cache')

        service_url = self._build_url(
            url=service_route,
            segments=self._get_segments(
                kwargs=kwargs
            ))

        response: httpx.Response = await self.make_request(
            url=service_url)

        _response = Response(
            response=response.content,
            status=response.status_code,
            headers=dict(response.headers))

        logger.info(f'Response: {_response._status}')
        return _response

    async def proxy(self, **kwargs):
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

        request.gateway_cors = self.configuration.cors
        status_code = None

        try:
            return await self.handle_request(**kwargs)
        except Exception as ex:
            return {
                'error': str(ex),
                'traceback': traceback.format_exc(),
                'type': str(type(ex))
            }, (status_code or 500)
