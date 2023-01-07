from domain.exceptions import RouteNotFoundException
from services.endpoint_reference import ServiceEndpointReference
from services.service_configuration import ServiceConfiguration
from services.route_map import RouteMap
from typing import List

from framework.logger.providers import get_logger
from utilities.utils import validate_leading_slash

logger = get_logger(__name__)


class ServiceMap:
    def __init__(
        self,
        container,
        service: ServiceConfiguration,
        service_name: str
    ):
        self.endpoint_reference = container.resolve(ServiceEndpointReference)
        self.service_name = service_name
        self.service_configuration = service
        self.__mapping = dict()
        self.route_maps: List[RouteMap] = list()

    @property
    def routes(
        self
    ):
        if not self.service_configuration:
            raise Exception('No service definition found')
        return self.service_configuration.routing

    @property
    def base_url(
        self
    ):
        return self.service_configuration.base_url

    def __getitem__(
        self,
        key
    ):
        if not key in self.__mapping:
            raise RouteNotFoundException(
                service=self.service_name,
                route=key)

        return self.__mapping[key]

    def __map_routes(
        self
    ):
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

    def __build_route_index(
        self
    ):
        index = dict()
        for route in self.route_maps:
            index[route.gateway_endpoint] = route
        self.__mapping = index

    def build(
        self
    ):
        logger.info('Building route map')
        self.__map_routes()
        self.__build_route_index()
        return self
