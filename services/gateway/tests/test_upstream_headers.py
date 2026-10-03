'''
Header hygiene in both directions.

These used to hold only for the one streaming route; the buffered path
forwarded `request.headers` verbatim.
'''

import pytest

INBOUND = {
    'Host': 'api.dan-leonard.com',
    'Authorization': 'Bearer token',
    'Content-Type': 'application/json',
    'Connection': 'keep-alive',
    'Transfer-Encoding': 'chunked',
    'Content-Length': '0',
    'TE': 'trailers',
    'Upgrade': 'websocket',
    'Proxy-Authorization': 'Basic abc',
}


async def request_headers(app, handler, extra=None):
    headers = dict(INBOUND)
    headers.update(extra or {})

    async with app.test_request_context('/ingress', method='GET', headers=headers):
        return handler._upstream_request_headers()


@pytest.mark.parametrize('header', [
    'Connection', 'Transfer-Encoding', 'TE', 'Upgrade', 'Proxy-Authorization',
])
async def test_hop_by_hop_headers_are_not_forwarded(app, handler, header):
    sent = await request_headers(app, handler)
    assert header.lower() not in {k.lower() for k in sent}


async def test_content_length_is_left_to_the_client(app, handler):
    '''httpx recalculates it from the body we hand it.'''

    sent = await request_headers(app, handler)
    assert 'content-length' not in {k.lower() for k in sent}


async def test_host_is_replaced_with_x_forwarded_host(app, handler):
    sent = await request_headers(app, handler)

    assert 'host' not in {k.lower() for k in sent}
    assert sent['X-Forwarded-Host'] == 'api.dan-leonard.com'


async def test_caller_supplied_forwarding_headers_are_dropped(app, handler):
    '''
    An upstream using X-Forwarded-For for allowlisting, rate limiting or audit
    logging must never see a value the caller chose.
    '''

    sent = await request_headers(app, handler, {
        'X-Forwarded-For': '1.2.3.4',
        'X-Forwarded-Proto': 'https',
        'X-Forwarded-Host': 'evil.example'})

    assert sent.get('X-Forwarded-For') != '1.2.3.4'
    assert sent['X-Forwarded-Host'] == 'api.dan-leonard.com'
    assert sent['X-Forwarded-Proto'] == 'http'


async def test_application_headers_are_preserved(app, handler):
    sent = await request_headers(app, handler)

    assert sent['Authorization'] == 'Bearer token'
    assert sent['Content-Type'] == 'application/json'


# --- response direction -------------------------------------------------


async def response_headers(app, handler, upstream_response, **headers):
    async with app.test_request_context('/ingress'):
        return handler._upstream_response_headers(upstream_response(**headers))


@pytest.mark.parametrize('header', [
    'Content-Length', 'Transfer-Encoding', 'Date', 'Server', 'Connection',
])
async def test_framing_and_identity_headers_are_stripped(
        app, handler, upstream_response, header):
    out = await response_headers(
        app, handler, upstream_response, **{header: 'x', 'X-App': 'keep'})

    assert header.lower() not in {k.lower() for k in out}
    assert out['X-App'] == 'keep'


async def test_upstream_cors_policy_is_passed_through(
        app, handler, upstream_response):
    '''The gateway does not enforce CORS -- the service's own policy stands.'''

    out = await response_headers(
        app, handler, upstream_response,
        **{'Access-Control-Allow-Origin': 'https://app.dan-leonard.com',
           'Vary': 'Origin'})

    assert out['Access-Control-Allow-Origin'] == 'https://app.dan-leonard.com'
    assert out['Vary'] == 'Origin'


async def test_internal_address_is_not_leaked_to_the_caller(
        app, handler, upstream_response):
    out = await response_headers(app, handler, upstream_response, **{'X-App': 'v'})
    assert 'x-remote-address' not in {k.lower() for k in out}
