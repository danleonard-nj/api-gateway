import json
from typing import Dict

from framework.configuration.configuration import Configuration
from framework.constants.constants import Environment
from framework.logger.providers import get_logger
from framework.validators.nulls import not_none
from utilities.constants import RouteConfigConstants

from services.gateway_map import GatewayMap
from services.proxy_handler import ProxyHandler
from services.service_configuration import ServiceConfiguration
from services.service_map import ServiceMap

logger = get_logger(__name__)


class ApiGateway:
    def __init__(self, container=None):
        not_none(container, 'container')
        self.container = container

        self.configuration = container.resolve(Configuration)

    def configure(
        self,
        app
    ) -> 'ApiGateway':
        '''
        Configure gateway and map routes defined
        in routing configuration
        '''

        self.app = app
        self.routing = self.load_route_config()
        self.gateway_map = GatewayMap()
        return self

    def load_route_config(
        self
    ) -> Dict:
        '''
        Load the routing configuration file
        '''

        if self.configuration.environment == Environment.DEVELOPMENT:
            logger.info(
                'Route config: loading development route configuration')
            config_path = RouteConfigConstants.ROUTE_CONFIG_DEVELOPMENT

        elif self.configuration.environment == Environment.LOCAL:
            logger.info('Route config: loading local route configuration')
            config_path = RouteConfigConstants.ROUTE_CONFIG_LOCAL

        else:
            logger.info(
                'Route configuration: loading production route configuration')
            config_path = RouteConfigConstants.ROUTE_CONFIG_PRODUCTION

        with open(config_path, 'r') as file:
            return json.loads(file.read())

    def build_maps(
        self
    ) -> None:
        '''
        Build and map the configured routes
        '''

        services = self.routing.get('services')
        not_none(services, 'services')

        logger.info('Building service maps')
        for service_key in services:

            service_configuration = ServiceConfiguration(
                service=services.get(service_key),
                name=service_key)

            not_none(self.configuration, 'configuration')
            logger.info(f'Constructing service map: {service_key}')

            service_map = ServiceMap(
                container=self.container,
                service=service_configuration,
                service_name=service_key).build()

            self.gateway_map.bind_service_map(
                service_map=service_map)

            proxy_handler = ProxyHandler(
                container=self.container,
                service=service_map)

            logger.info(
                f'Configuring proxy: mapped routes: {len(service_map.route_maps)}')

            for route in service_map.route_maps:
                logger.info(
                    f'Binding proxy object to route: {route.gateway_endpoint}')

                route.map_route(
                    app=self.app,
                    proxy_request=proxy_handler.proxy)
