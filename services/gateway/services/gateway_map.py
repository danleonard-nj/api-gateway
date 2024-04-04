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

        self._services = services or []
        self._mapping = dict()

    def __getitem__(self, key: str) -> str:
        route = self.get_mapped_route(key)
        if not route:
            raise Exception(
                f'Failed to find mapped service for endpoint: {key}')
        return route

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

        return self._mapping[gateway_endpoint]

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
        self._services.append(service_map)

        for gateway_route in service_map.mapping:
            self._mapping[gateway_route] = service_map.mapping[gateway_route]
