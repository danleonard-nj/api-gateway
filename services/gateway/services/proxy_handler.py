import traceback
from typing import Dict

import httpx
from framework.clients.cache_client import CacheClientAsync
from framework.clients.http_client import HttpClient
from framework.crypto.hashing import md5
from framework.di.service_provider import ServiceProvider
from framework.exceptions.nulls import ArgumentNullException
from framework.logger.providers import get_logger
from framework.uri.uri import Uri
from quart import Response, request

from services.route_map import RouteMap
from services.service_map import ServiceMap

logger = get_logger(__name__)


class ProxyHandler:
    def __init__(
        self,
        service_provider: ServiceProvider,
        service: ServiceMap
    ):
        self.__service = service
        self.__configuration = service.service_configuration

        self.__http_client = HttpClient()
        self.__cache_client = service_provider.resolve(
            CacheClientAsync)

    def __get_rule(
        self
    ):
        rule = request.url_rule.rule
        if not rule:
            raise Exception('No Werkzeug mapped rule')
        return rule

    def __parse_interpolated_segments(
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

    def __build_url(
        self,
        url: str,
        segments: Dict
    ) -> str:
        ArgumentNullException.if_none_or_whitespace('url', url)

        route_uri = Uri(
            url=f'{self.__service.base_url}{url}')

        if request.args:
            route_uri.query = dict(request.args)

        if (self.__configuration.port
                and self.__configuration.port != 0):
            route_uri.port = self.__configuration.port

        proxy_url = route_uri.get_url()
        if any(segments):
            proxy_url = self.__parse_interpolated_segments(
                url=proxy_url,
                segments=segments)

        return proxy_url

    async def make_request(
        self,
        url: str
    ):
        data = await request.get_data()

        if data:
            response = await self.__http_client.request(
                method=request.method,
                url=url,
                data=data,
                headers=request.headers,
                timeout=None)
        else:
            response = await self.__http_client.request(
                method=request.method,
                url=url,
                headers=request.headers,
                timeout=None)

        logger.info(
            f'Request: {response.request.method}: {response.request.url}')

        logger.info(f'Service: {response.status_code}')
        logger.info(f'Service: {response.elapsed} elapsed')
        return response

    def __request_hash_key(
        self,
        ingress_path: str,
        kwargs: Dict
    ):
        ArgumentNullException.if_none_or_whitespace(
            ingress_path, 'ingress_path')

        return md5(f'{ingress_path}{kwargs}')

    async def __get_cache(
        self,
        hash_key: str
    ) -> str:
        ArgumentNullException.if_none_or_whitespace(hash_key, 'hash_key')

        cached_route = await self.__cache_client.get_cache(
            key=hash_key)
        return cached_route

    async def __set_cache(
        self,
        hash_key: str,
        service_route: str
    ) -> str:
        ArgumentNullException.if_none_or_whitespace(hash_key, 'hash_key')
        ArgumentNullException.if_none_or_whitespace(
            service_route, 'service_route')

        await self.__cache_client.set_cache(
            key=hash_key,
            value=service_route,
            ttl=60 * 24)

    def __get_segments(
        self,
        kwargs: Dict
    ):
        return {
            k: v for k, v in kwargs.items()
            if k != 'container'
        }

    async def handle_request(
        self,
        **kwargs
    ):
        ingress_route = self.__get_rule()

        hash_key = self.__request_hash_key(
            ingress_path=ingress_route,
            kwargs=kwargs)

        cached_route = await self.__get_cache(
            hash_key=hash_key)

        if not cached_route:
            logger.info('No cached endpoint, fetching from route map')

            route: RouteMap = self.__service[ingress_route]
            service_route = route.service_endpoint

            await self.__set_cache(
                hash_key=hash_key,
                service_route=route.service_endpoint)
        else:
            service_route = cached_route
            logger.info('Endpoint returned from cache')

        service_url = self.__build_url(
            url=service_route,
            segments=self.__get_segments(
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

        request.gateway_cors = self.__configuration.cors
        status_code = None

        try:
            return await self.handle_request(**kwargs)
        except Exception as ex:
            return {
                'error': str(ex),
                'traceback': traceback.format_exc(),
                'type': str(type(ex))
            }, (status_code or 500)
