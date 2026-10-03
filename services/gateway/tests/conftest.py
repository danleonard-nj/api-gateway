import types

import pytest
from quart import Quart

from services.proxy_handler import ProxyHandler


@pytest.fixture
def app():
    return Quart(__name__)


@pytest.fixture
def handler():
    '''
    A ProxyHandler with only the collaborators its URL and header logic
    actually touches.

    `__init__` resolves a cache client out of the DI container, which the
    URL-building and header paths never use.  Bypassing it keeps these tests
    on the real methods without standing up a container or a Redis.
    '''

    proxy = object.__new__(ProxyHandler)
    proxy._service_map = types.SimpleNamespace(
        base_url='http://upstream',
        service_name='svc')
    proxy._configuration = types.SimpleNamespace(
        port=None,
        streaming=False,
        stream_read_timeout=None)

    return proxy


@pytest.fixture
def upstream_response():
    '''Build a stand-in for an httpx response's header bag.'''

    def _build(**headers):
        return types.SimpleNamespace(headers=headers)

    return _build
