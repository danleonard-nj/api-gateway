from framework.clients.cache_client import CacheClientAsync
from framework.configuration.configuration import Configuration
from framework.di.service_collection import ServiceCollection
from framework.di.static_provider import ProviderBase
from httpx import AsyncClient
from services.endpoint_reference import ServiceEndpointReference


def configure_http_client(container):
    return AsyncClient(timeout=None)


class ContainerProvider(ProviderBase):
    @classmethod
    def configure_container(cls):
        descriptors = ServiceCollection()

        descriptors.add_singleton(Configuration)

        descriptors.add_singleton(
            dependency_type=AsyncClient,
            factory=configure_http_client)

        descriptors.add_singleton(ServiceEndpointReference)
        descriptors.add_singleton(CacheClientAsync)

        return descriptors
