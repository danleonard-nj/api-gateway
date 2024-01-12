import json
import os

from framework.configuration.configuration import Configuration
from framework.di.service_provider import ServiceProvider
from framework.exceptions.nulls import ArgumentNullException
from framework.logger.providers import get_logger
from framework.validators.nulls import not_none

from services.gateway_map import GatewayMap
from services.proxy_handler import ProxyHandler
from services.service_configuration import ServiceConfiguration
from services.service_map import ServiceMap

logger = get_logger(__name__)


class ApiGatewayConfigurationException(Exception):
    def __init__(
        self,
        message: str
    ):
        super().__init__(message)

class ApiGateway:
    def __init__(
        self,
        service_provider: ServiceProvider
    ):
        self.__service_provider = service_provider
        self.__configuration = service_provider.resolve(Configuration)

    def configure(
        self,
        app
    ) -> 'ApiGateway':
        '''
        Configure gateway and map routes defined
        in routing configuration
        '''

        self.app = app
        self.routing = self.__compile_route_configs()
        self.gateway_map = GatewayMap()
        return self

    def __load_route_config_services(
        self,
        filename: str
    ):
        ArgumentNullException.if_none_or_whitespace(filename, 'filename')

        with open(filename, 'r') as file:
            config = json.loads(file.read())
            return config.get('services')

    def __compile_route_configs(
        self
    ):
        configs = dict()

        for base_filename in os.listdir('mapping'):
            filename = f'./mapping/{base_filename}'
            logger.info(f"Loading routes from config: {filename}")

            config = self.__load_route_config_services(
                filename=filename)

            configs |= config
            logger.info(f"{len(config)} service routings parsed: {filename}")

        return {
            'services': configs
        }

    def build_maps(
        self
    ) -> None:
        '''
        Build and map the configured routes
        '''

        services = self.routing.get('services')
        
        if services is None:
            raise ApiGatewayConfigurationException(
                'No services defined in routing configuration')

        logger.info('Building service maps')
        for service_key in services:

            service_configuration = ServiceConfiguration(
                service=services.get(service_key),
                name=service_key)

            if service_configuration is None:
                raise ApiGatewayConfigurationException(
                    f'No configuration found for service: {service_key}')
            
            logger.info(f'Creating map for service: {service_key}')

            service_map = ServiceMap(
                container=self.__service_provider,
                service=service_configuration,
                service_name=service_key).build()

            self.gateway_map.bind_service_map(
                service_map=service_map)

            proxy_handler = ProxyHandler(
                service_provider=self.__service_provider,
                service=service_map)

            logger.info(
                f'Configuring proxy: mapped routes: {len(service_map.route_maps)}')

            for route in service_map.route_maps:
                logger.info(
                    f'Binding proxy view function to route: {route.gateway_endpoint}')

                route.map_route(
                    app=self.app,
                    proxy_request=proxy_handler.proxy)
