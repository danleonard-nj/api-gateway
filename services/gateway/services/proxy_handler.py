import asyncio
import traceback
from typing import Dict

from domain.cache import CacheKey
from framework.clients.cache_client import CacheClientAsync
from framework.di.service_provider import ServiceProvider
from framework.exceptions.nulls import ArgumentNullException
from framework.logger.providers import get_logger
from framework.uri.uri import Uri
from httpx import AsyncClient
from quart import Response, request
from services.service_map import ServiceMap

logger = get_logger(__name__)


def fire_task(func):
    asyncio.create_task(func)


class ProxyHandler:
    def __init__(
        self,
        service_provider: ServiceProvider,
        service: ServiceMap
    ):
        self._provider = service_provider

        self._service = service
        self._configuration = service.service_configuration

        self.__cache_client = service_provider.resolve(
            CacheClientAsync)

    def _parse_interpolated_segments(
        self,
        url: str,
        segments: Dict
    ):
        ArgumentNullException.if_none_or_whitespace(url, 'url')
        ArgumentNullException.if_none(segments, 'segments')

        interp_url = url
        for segment in segments:
            repl = f'<{segment}>'
            interp_url = interp_url.replace(
                repl,
                segments[segment])

        return interp_url

    def _build_url(
        self,
        url: str,
        segments: Dict
    ) -> str:
        ArgumentNullException.if_none_or_whitespace('url', url)

        route_uri = Uri(
            url=f'{self._service.base_url}{url}')

        # Handle query params
        if request.args:
            logger.info(f'Query params: {request.args}')
            route_uri.query = dict(request.args)

        # Handle non-standard port mapping
        if (self._configuration.port
                and self._configuration.port != 0):
            route_uri.port = self._configuration.port

        # Build the proxy endpoint
        proxy_url = route_uri.get_url()

        # Handle route segments
        if any(segments):
            proxy_url = self._parse_interpolated_segments(
                url=proxy_url,
                segments=segments)

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

        response = await client.request(
            method=request.method,
            url=url,
            data=data,
            headers=request.headers,
            timeout=None)

        logger.info(
            f'Request: {response.request.method}: {response.request.url}')

        logger.info(f'Service: {response.status_code}')
        logger.info(f'Service: {response.elapsed} elapsed')
        return response

    async def _get_cache(
        self,
        hash_key: str
    ) -> str:
        ArgumentNullException.if_none_or_whitespace(hash_key, 'hash_key')

        try:
            cached_route = await self.__cache_client.get_cache(
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
            await self.__cache_client.set_cache(
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
        ingress_route: str,
        route_params: Dict
    ):
        # Create cache key for ingress route
        cache_key = CacheKey.mapped_route(
            ingress_path=ingress_route,
            kwargs=route_params)

        logger.info(f'Route cache key: {cache_key}')

        cached_route = await self._get_cache(
            hash_key=cache_key)

        if cached_route is not None:
            logger.info(f'Using cached route: {cached_route}')
            return cached_route

        # Get the route mapping definition
        route_mapping = self._service[ingress_route]
        logger.info(f'Service: {route_mapping.service_endpoint}')

        # Fire and forget the write to cache
        fire_task(self._set_cache(
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
            ingress_route=ingress_route,
            route_params=kwargs)

        logger.info(f'Service route: {service_route}')

        service_url = self._build_url(
            url=service_route,
            segments=self._get_segments_from_kwargs(
                kwargs=kwargs
            ))

        logger.info(f'Service URL: {service_url}')

        service_response = await self._send_request(
            url=service_url)

        # Forward sender address
        headers = dict(service_response.headers)
        headers['X-Remote-Address'] = request.remote_addr

        gateway_response = Response(
            response=service_response.content,
            status=service_response.status_code,
            headers=dict(service_response.headers))

        logger.info(f'Response: {gateway_response.status_code}: {
                    service_response.elapsed}')
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

        # Apply defined CORS rules
        request.gateway_cors = self._configuration.cors
        status_code = None

        try:
            return await self.handle_request(**kwargs)
        except Exception as ex:
            return {
                'error': str(ex),
                'traceback': traceback.format_exc(),
                'type': str(type(ex))
            }, (status_code or 500)
