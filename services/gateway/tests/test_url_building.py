'''
Upstream URL construction.

The interesting cases are all the same shape: a route segment is caller
controlled, and must end up as *data* in the upstream path rather than as URL
syntax.
'''

import pytest

ROUTE = '/api/journal/entries/<entry_id>'


async def build(app, handler, segments, query=''):
    async with app.test_request_context(f'/ingress{query}', method='GET'):
        return handler._build_url(url=ROUTE, segments=segments)


async def test_plain_segment_is_substituted(app, handler):
    url = await build(app, handler, {'entry_id': '1'})
    assert url == 'http://upstream/api/journal/entries/1'


async def test_question_mark_in_segment_cannot_start_a_query_string(app, handler):
    url = await build(app, handler, {'entry_id': '1?admin=true'})

    assert '?' not in url
    assert url.endswith('/1%3Fadmin%3Dtrue')


async def test_hash_in_segment_cannot_truncate_the_url(app, handler):
    url = await build(app, handler, {'entry_id': '1#'})

    assert '#' not in url
    assert url.endswith('/1%23')


async def test_segment_cannot_displace_gateway_query_params(app, handler):
    '''The injected params must not be parsed by upstream, and ours must survive.'''

    url = await build(
        app, handler,
        {'entry_id': '1?role=admin&x=1'},
        query='?tenant=victim')

    assert url.count('?') == 1
    assert url.endswith('?tenant=victim')
    assert 'role=admin' not in url
    assert '&' not in url


async def test_every_segment_is_encoded_independently(app, handler):
    async with app.test_request_context('/ingress'):
        url = handler._build_url(
            url='/api/aks/<namespace>/<pod>/logs',
            segments={'namespace': 'kube-system?all=1', 'pod': 'web/../etc'})

    assert url == (
        'http://upstream/api/aks/'
        'kube-system%3Fall%3D1/web%2F..%2Fetc/logs')


async def test_traversal_segment_stays_one_path_segment(app, handler):
    url = await build(app, handler, {'entry_id': '../../admin'})

    assert '/../' not in url
    assert url.endswith('/..%2F..%2Fadmin')


@pytest.mark.parametrize('value', ['a b', 'ünïcode', 'a%2Fb', 'a+b'])
async def test_awkward_values_survive_a_round_trip(app, handler, value):
    from urllib.parse import unquote

    url = await build(app, handler, {'entry_id': value})
    assert unquote(url.rsplit('/', 1)[-1]) == value


async def test_request_query_params_are_forwarded(app, handler):
    url = await build(app, handler, {'entry_id': '1'}, query='?a=1')
    assert url.endswith('?a=1')


async def test_non_standard_port_is_applied(app, handler):
    handler._configuration.port = 8080

    url = await build(app, handler, {'entry_id': '1'})
    assert url.startswith('http://upstream:8080/')


async def test_repeated_query_params_are_all_forwarded(app, handler):
    '''
    Flattening the inbound MultiDict dropped every value but the first, so a
    service filtering on `?tag=a&tag=b` silently saw only half the request.
    '''

    url = await build(app, handler, {'entry_id': '1'}, query='?tag=a&tag=b&x=1')

    assert url.endswith('?tag=a&tag=b&x=1')


async def test_query_param_values_are_encoded(app, handler):
    url = await build(app, handler, {'entry_id': '1'}, query='?q=a%20b%26c%3Dd')

    assert url.count('?') == 1
    assert url.endswith('?q=a+b%26c%3Dd')
