from typing import List

from domain.exceptions import RouteNotFoundException
from framework.di.service_provider import ServiceProvider
from framework.exceptions.nulls import ArgumentNullException
from framework.logger.providers import get_logger
from services.endpoint_reference import ServiceEndpointReference
from services.route_map import RouteMap
from services.service_configuration import ServiceConfiguration
from utilities.utils import validate_leading_slash

logger = get_logger(__name__)


class ServiceMap:
    @property
    def mapping(
        self
    ) -> dict[str, RouteMap]:
        '''
        Mapping of gateway endpoints to route maps
        '''

        return self._mapping

    @property
    def base_url(
        self
    ) -> str:
        '''
        Base URL for the service routes defined in the
        service configuration JSON
        '''

        return self.service_configuration.base_url

    @property
    def route_maps(
        self
    ) -> List[RouteMap]:
        '''
        List of route maps for the service
        '''

        return self._route_maps

    def __init__(
        self,
        service_provider: ServiceProvider,
        service: ServiceConfiguration,
        service_name: str
    ):
        self.service_name = service_name
        self.service_configuration = service

        self.endpoint_reference: ServiceEndpointReference = service_provider.resolve(
            ServiceEndpointReference)

        self._route_maps: List[RouteMap] = list()
        self._mapping: dict[str, RouteMap] = dict()

        self._map_routes()

    def __getitem__(
        self,
        key: str
    ) -> RouteMap:
        '''
        Get a route by key (gateway endpoint)
        '''

        ArgumentNullException.if_none_or_whitespace(key, 'key')

        if not key in self._mapping:
            raise RouteNotFoundException(
                service=self.service_name,
                route=key)

        return self._mapping[key]

    def _map_routes(
        self
    ) -> None:
        '''
        Map the service routes to endpoint references
        '''

        logger.info(f'Routes to map: {len(self.service_configuration.routing)}')

        for route in self.service_configuration.routing:
            route_map = RouteMap(route=route)

            self.endpoint_reference.add(
                service_configuration=self.service_configuration,
                endpoint_id=route_map.endpoint_id)

            validate_leading_slash(url=route_map.service_endpoint)
            validate_leading_slash(url=route_map.gateway_endpoint)

            self._route_maps.append(route_map)
            self._mapping[route_map.gateway_endpoint] = route_map
