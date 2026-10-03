'''
CORS is not enforced at the gateway.

The service owns its own policy, which means preflights have to reach it --
Quart's automatic OPTIONS handling would answer them itself, and the service
would never see the request.
'''

from quart import Quart, request

from services.route_map import RouteMap


def build_app(allowed_methods):
    app = Quart(__name__)
    seen = []

    async def view(**kwargs):
        seen.append(request.method)
        return {'ok': True}, 200

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


async def test_gateway_injects_no_cors_headers_of_its_own():
    gateway, _ = build_app(['GET'])

    response = await gateway.test_client().get(
        '/api/thing/1', headers={'Origin': 'https://evil.example'})

    assert 'Access-Control-Allow-Origin' not in response.headers
