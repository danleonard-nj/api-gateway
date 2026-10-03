'''Route mapping, cache keying, and config validation.'''

import pytest

from domain.cache import CacheKey
from utilities.utils import validate_leading_slash


def test_cache_key_ignores_segment_values():
    '''
    The mapping resolves from static config, so it is identical for every value
    of a segment.  Keying on the values produced one entry per distinct value:
    unbounded, caller-driven growth holding the same string over and over.
    '''

    first = CacheKey.mapped_route(service_name='svc', ingress_path='/api/x/<id>')
    second = CacheKey.mapped_route(service_name='svc', ingress_path='/api/x/<id>')

    assert first == second


def test_cache_key_separates_services():
    assert (CacheKey.mapped_route(service_name='a', ingress_path='/api/x')
            != CacheKey.mapped_route(service_name='b', ingress_path='/api/x'))


def test_cache_key_separates_routes():
    assert (CacheKey.mapped_route(service_name='svc', ingress_path='/api/x')
            != CacheKey.mapped_route(service_name='svc', ingress_path='/api/y'))


def test_leading_slash_accepted():
    validate_leading_slash('/api/x')


@pytest.mark.parametrize('value', ['api/x', '', None])
def test_missing_or_relative_endpoint_is_a_config_error(value):
    '''
    A route config that omits an endpoint used to raise TypeError from a
    subscript, which read as a crash rather than as the config error it is.
    '''

    with pytest.raises(Exception, match='must begin with a leading slash'):
        validate_leading_slash(value)
