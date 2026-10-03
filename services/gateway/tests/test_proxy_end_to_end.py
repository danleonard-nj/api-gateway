'''
The whole proxy path against a mocked upstream: route resolution, URL
construction, header rewriting and response translation together.
'''

import types

import httpx2
import pytest
from httpx2 import AsyncClient
from quart import Quart

from services.proxy_handler import ProxyHandler
from services.route_map import RouteMap

GATEWAY_ROUTE = '/api/tools/journal/entries/<entry_id>'
SERVICE_ROUTE = '/api/journal/entries/<entry_id>'


class FakeServiceMap:
    '''Minimal stand-in: ProxyHandler indexes this by ingress rule.'''

    def __init__(self, route):
        self._route = route
        self.base_url = 'http://upstream'
        self.service_name = 'kube-tools'

    def __getitem__(self, key):
        return self._route


def make_client(handler):
    return AsyncClient(transport=httpx2.MockTransport(handler))


@pytest.fixture
def gateway():
    '''An app with one proxied route and a recording upstream.'''

    seen = {}

    async def upstream(req):
        seen['method'] = req.method
        seen['url'] = str(req.url)
        seen['headers'] = dict(req.headers)
        seen['body'] = req.content
        return httpx2.Response(
            201,
            headers={'Content-Type': 'application/json',
                     'Content-Length': '999',
                     'Server': 'upstream/1.0',
                     'Access-Control-Allow-Origin': 'https://app.dan-leonard.com'},
            content=b'{"ok":true}')

    route = RouteMap({
        'gateway_endpoint': GATEWAY_ROUTE,
        'service_endpoint': SERVICE_ROUTE,
        'allowed_methods': ['GET', 'POST'],
    })

    proxy = object.__new__(ProxyHandler)
    proxy._provider = types.SimpleNamespace(
        resolve=lambda _: make_client(upstream))
    proxy._service_map = FakeServiceMap(route)
    proxy._configuration = types.SimpleNamespace(
        port=None, streaming=False, stream_read_timeout=None)

    # No cache: exercise the resolution path rather than a warm key.
    async def miss(**kwargs):
        return None

    proxy._cache_client = types.SimpleNamespace(get_cache=miss, set_cache=miss)

    app = Quart(__name__)
    route.map_route(app=app, proxy_request=proxy.proxy)

    return app, seen, proxy


async def test_request_reaches_the_mapped_service_route(gateway):
    app, seen, _ = gateway

    response = await app.test_client().get('/api/tools/journal/entries/42')

    assert response.status_code == 201
    assert seen['url'] == 'http://upstream/api/journal/entries/42'


async def test_status_and_body_are_forwarded(gateway):
    app, _, proxy = gateway

    response = await app.test_client().get('/api/tools/journal/entries/42')

    assert response.status_code == 201
    assert await response.get_json() == {'ok': True}


async def test_injected_segment_does_not_reach_upstream_as_syntax(gateway):
    app, seen, _ = gateway

    await app.test_client().get('/api/tools/journal/entries/42%3Fadmin%3Dtrue')

    assert seen['url'] == (
        'http://upstream/api/journal/entries/42%3Fadmin%3Dtrue')
    assert 'admin=true' not in seen['url']


async def test_spoofed_forwarding_header_does_not_reach_upstream(gateway):
    app, seen, _ = gateway

    await app.test_client().get(
        '/api/tools/journal/entries/42',
        headers={'X-Forwarded-For': '1.2.3.4'})

    assert seen['headers'].get('x-forwarded-for') != '1.2.3.4'
    assert 'host' not in seen['headers'] or \
        seen['headers']['host'] == 'upstream'


async def test_upstream_cors_survives_and_framing_does_not(gateway):
    app, _, proxy = gateway

    response = await app.test_client().get('/api/tools/journal/entries/42')

    assert response.headers['Access-Control-Allow-Origin'] == \
        'https://app.dan-leonard.com'
    assert 'Server' not in response.headers
    assert response.headers.get('Content-Length') != '999'


async def test_upstream_failure_becomes_a_gateway_error(gateway):
    app, _, proxy = gateway

    async def unreachable(req):
        raise httpx2.ConnectTimeout('upstream down')

    proxy._provider = types.SimpleNamespace(
        resolve=lambda _: make_client(unreachable))

    response = await app.test_client().get('/api/tools/journal/entries/42')

    assert response.status_code == 504
    assert (await response.get_json())['error'] == 'Gateway timeout'


async def test_request_body_is_forwarded(gateway):
    app, seen, _ = gateway

    await app.test_client().post(
        '/api/tools/journal/entries/42',
        json={'title': 'entry'})

    assert seen['body'] == b'{"title": "entry"}'
    assert seen['headers']['content-length'] == '18'


async def test_repeated_query_params_reach_upstream(gateway):
    app, seen, _ = gateway

    await app.test_client().get('/api/tools/journal/entries/42?tag=a&tag=b')

    assert seen['url'].endswith('?tag=a&tag=b')
