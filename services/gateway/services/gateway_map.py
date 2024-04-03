from services.service_map import ServiceMap
from typing import List
from framework.exceptions.nulls import ArgumentNullException
from framework.logger.providers import get_logger

logger = get_logger(__name__)


class GatewayMap:
    def __init__(
        self,
        services: List[ServiceMap] = None
    ):
        '''
        Top-level container for routing configuration
        for mapped services

        Args:
            services (List[ServiceMap], optional): the
            service mapping parsed from routing config
        '''

        self.services = services or []

        self.gateway_map = self.build_gateway_map()

    def __getitem__(self, key: str) -> str:
        route = self.get_mapped_route(key)
        if not route:
            raise Exception(
                f'Failed to find mapped service for endpoint: {key}')
        return route

    def build_gateway_map(
        self
    ) -> dict[str, str]:
        '''
        Build the gateway map from the service map
        configurations
        '''

        gateway_map = dict()
        for service in self.services:
            for gateway_route in service.mapping:
                gateway_map[gateway_route] = service.mapping[gateway_route]

        return gateway_map

    def get_mapped_route(
        self,
        gateway_endpoint: str
    ) -> str:
        '''
        Get the mapped service endpoint from
        the provided gateway endpoint

        Args:
            endpoint (str): gateway endpoint

        Returns:
            str: mapped service endpoint
        '''

        # for service in self.services:
        #     if endpoint in service._mapping:
        #         logger.info(f'{service.base_url}: route match')
        #         return service._mapping[endpoint]

        # TODO: Benchmarks for this approach vs. looping
        return self.gateway_map[gateway_endpoint]

    def bind_service_map(
        self,
        service_map: ServiceMap
    ) -> None:
        '''
        Bind a service map to the gateway service
        routing

        Args:
            service_map (ServiceMap): service map
            from the route config
        '''

        ArgumentNullException.if_none(service_map, 'service_map')

        logger.info(f'Binding service map to gateway map: {service_map.service_name}')
        self.services.append(service_map)
