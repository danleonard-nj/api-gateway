import json
import os

from framework.configuration.configuration import Configuration
from framework.di.service_provider import ServiceProvider
from framework.exceptions.nulls import ArgumentNullException
from framework.logger.providers import get_logger
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
        app,
        service_provider: ServiceProvider
    ):
        self._app = app
        self._service_provider = service_provider
        self._gateway_map = GatewayMap()

    def _load_route_config_services(
        self,
        filename: str
    ):
        ArgumentNullException.if_none_or_whitespace(filename, 'filename')

        with open(filename, 'r') as file:
            config = json.loads(file.read())
            return config.get('services')

    def _gather_route_configs(
        self
    ):
        configs = dict()

        for base_filename in os.listdir('mapping'):
            filename = f'./mapping/{base_filename}'
            logger.info(f"Loading routes from config: {filename}")

            config = self._load_route_config_services(
                filename=filename)

            configs |= config
            logger.info(f"{len(config)} service routings parsed: {filename}")

        return configs

    def build_maps(
        self
    ) -> 'ApiGateway':
        '''
        Build and map the configured routes
        '''

        services = self._gather_route_configs()

        if services is None:
            raise ApiGatewayConfigurationException(
                'No services defined in routing configuration')

        logger.info('Building service maps')
        for service_key in services:

            # Create the service configuration for the mapped sevice
            service_configuration = ServiceConfiguration(
                service=services.get(service_key),
                name=service_key)

            # if service_configuration is None:
            #     raise ApiGatewayConfigurationException(
            #         f'No configuration found for service: {service_key}')

            logger.info(f'Creating map for service: {service_key}')

            # Build the service map
            service_map = ServiceMap(
                service_provider=self._service_provider,
                service=service_configuration,
                service_name=service_key)

            # Bind this service map to the gateway maps
            self._gateway_map.bind_service_map(
                service_map=service_map)

            proxy_handler = ProxyHandler(
                service_provider=self._service_provider,
                service_map=service_map)

            for route in service_map.route_maps:
                logger.info(f'Mapped route: {route.gateway_endpoint} -> {route.service_endpoint}')

                route.map_route(
                    app=self._app,
                    proxy_request=proxy_handler.proxy)

        return self
