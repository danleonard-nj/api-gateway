from services.service_map import ServiceMap
from typing import List

from framework.validators.nulls import not_none
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
        self.index = dict()

    def __getitem__(self, key: str) -> str:
        route = self.get_mapped_route(key)
        if not route:
            raise Exception(
                f'Failed to find mapped service for endpoint: {key}')
        return route

    def get_mapped_route(
        self,
        endpoint: str
    ) -> str:
        '''
        Get the mapped service endpoint from
        the provided gateway endpoint

        Args:
            endpoint (str): gateway endpoint

        Returns:
            str: mapped service endpoint
        '''

        for service in self.services:
            if endpoint in service._mapping:
                logger.info(f'{service.base_url}: route match')
                return service._mapping[endpoint]

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

        logger.info('Binding service map to gateway map')
        not_none(service_map, 'service_map')

        logger.info(f'Bound service map: {service_map.service_name}')
        self.services.append(service_map)
