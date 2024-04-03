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
    def __init__(
        self,
        service_provider: ServiceProvider,
        service: ServiceConfiguration,
        service_name: str
    ):
        self.service_name = service_name
        self.service_configuration = service
        self.route_maps: List[RouteMap] = list()

        self._mapping: dict[str, RouteMap] = dict()

        self.endpoint_reference: ServiceEndpointReference = service_provider.resolve(
            ServiceEndpointReference)

    @property
    def mapping(
        self
    ) -> dict[str, RouteMap]:
        '''
        Mapping of gateway endpoints to route maps
        '''

        return self._mapping

    @property
    def routes(
        self
    ) -> list[dict]:
        '''
        Route definitions list for a service configuration
        as defined in the service configuration JSON
        '''

        if not self.service_configuration:
            raise Exception('No service definition found')
        return self.service_configuration.routing

    @property
    def base_url(
        self
    ) -> str:
        '''
        Base URL for the service routes defined in the
        service configuration JSON
        '''

        return self.service_configuration.base_url

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

        logger.info(f'Routes to map: {len(self.routes)}')
        for route in self.routes:
            mapped = RouteMap(
                route=route)

            self.endpoint_reference.add(
                service_configuration=self.service_configuration,
                endpoint_id=mapped.endpoint_id)

            validate_leading_slash(
                url=mapped.service_endpoint)
            validate_leading_slash(
                url=mapped.gateway_endpoint)

            logger.info(
                f'Mapped: {mapped.gateway_endpoint}')
            self.route_maps.append(mapped)

    def _build_route_index(
        self
    ) -> dict[str, RouteMap]:
        '''
        Build the lookup from gateway endpoint to route map
        '''

        self._mapping = dict()

        for route in self.route_maps:
            self._mapping[route.gateway_endpoint] = route

    def build(
        self
    ):
        logger.info('Building route map')
        self._map_routes()
        self._build_route_index()
        return self
