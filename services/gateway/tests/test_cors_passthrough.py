'''
A service with its own CORS policy owns it; one without gets the gateway's.

Preflights have to reach the service -- Quart's automatic OPTIONS handling
would answer them itself, and the service would never see the request.  The
gateway's open default is filled in only when the upstream sent no policy.
'''

from quart import Quart, request

from services.route_map import RouteMap
from utilities.cors import apply_default_cors


def build_app(allowed_methods, upstream_headers=None):
    app = Quart(__name__)
    app.after_request(apply_default_cors)
    seen = []

    async def view(**kwargs):
        seen.append(request.method)
        return {'ok': True}, 200, dict(upstream_headers or {})

    RouteMap({
        'gateway_endpoint': '/api/thing/<thing_id>',
        'service_endpoint': '/thing/<thing_id>',
        'allowed_methods': allowed_methods,
    }).map_route(app=app, proxy_request=view)

    return app, seen


async def test_options_reaches_the_service(app):
    gateway, seen = build_app(['GET'])

    response = await gateway.test_client().options('/api/thing/1')

    assert seen == ['OPTIONS'], 'preflight was answered by the gateway'
    assert response.status_code == 200


async def test_options_is_added_when_not_configured():
    gateway, _ = build_app(['GET'])

    rule = next(r for r in gateway.url_map.iter_rules()
                if r.rule == '/api/thing/<thing_id>')
    assert 'OPTIONS' in rule.methods
    assert rule.provide_automatic_options is False


async def test_options_is_not_duplicated_when_configured():
    gateway, seen = build_app(['GET', 'OPTIONS'])

    await gateway.test_client().options('/api/thing/1')
    assert seen == ['OPTIONS']


async def test_configured_methods_are_still_enforced():
    gateway, seen = build_app(['GET'])

    response = await gateway.test_client().post('/api/thing/1')

    assert response.status_code == 405
    assert seen == []


async def test_default_policy_applied_when_upstream_has_none():
    gateway, _ = build_app(['GET'])

    response = await gateway.test_client().get(
        '/api/thing/1', headers={'Origin': 'https://app.example'})

    assert response.headers['Access-Control-Allow-Origin'] == '*'
    assert response.headers['Access-Control-Allow-Headers'] == '*'
    assert response.headers['Access-Control-Allow-Methods'] == '*'


async def test_default_policy_applied_to_forwarded_preflight():
    gateway, seen = build_app(['GET'])

    response = await gateway.test_client().options(
        '/api/thing/1',
        headers={
            'Origin': 'https://app.example',
            'Access-Control-Request-Method': 'GET',
        })

    assert seen == ['OPTIONS']
    assert response.headers['Access-Control-Allow-Origin'] == '*'


async def test_upstream_policy_passes_through_untouched():
    gateway, _ = build_app(['GET'], upstream_headers={
        'Access-Control-Allow-Origin': 'https://app.example',
        'Access-Control-Allow-Methods': 'GET',
    })

    response = await gateway.test_client().get(
        '/api/thing/1', headers={'Origin': 'https://app.example'})

    assert response.headers['Access-Control-Allow-Origin'] == \
        'https://app.example'
    assert response.headers['Access-Control-Allow-Methods'] == 'GET'
    # Not merged in: the service's policy is its own, not widened by ours.
    assert 'Access-Control-Allow-Headers' not in response.headers
