from framework.dependency_injection.provider import ProviderBase
from framework.dependency_injection.container import Container
from framework.configuration.configuration import Configuration
from framework.middleware.authorization import AuthMiddleware
from framework.clients.cache_client import CacheClientAsync

from quart import Quart, request
from services.endpoint_reference import ServiceEndpointReference


class ContainerProvider(ProviderBase):
    @classmethod
    def configure_container(cls):
        container = Container()

        container.add_singleton(Configuration)
        container.add_singleton(ServiceEndpointReference)
        container.add_singleton(CacheClientAsync)

        return container.build()


def add_container_hook(app: Quart):
    def inject_container():
        if request.view_args != None:
            request.view_args['container'] = ContainerProvider.get_container()

    app.before_request_funcs.setdefault(
        None, []).append(
            inject_container)
