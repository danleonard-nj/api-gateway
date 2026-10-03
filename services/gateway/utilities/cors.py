ACCESS_CONTROL_ALLOW_ORIGIN = 'Access-Control-Allow-Origin'

# The open policy the gateway has always applied.  Most upstream services
# (kube-tools and the other Quart services) set no CORS headers of their own
# and rely on these to be reachable from the browser at all.
DEFAULT_CORS_HEADERS = {
    ACCESS_CONTROL_ALLOW_ORIGIN: '*',
    'Access-Control-Allow-Headers': '*',
    'Access-Control-Allow-Methods': '*',
}


def apply_default_cors(response):
    '''
    Fill in the gateway's default CORS policy when the upstream has none.

    An upstream that sends its own `Access-Control-Allow-Origin` owns its
    policy, and its headers pass through untouched -- a partial merge with
    the defaults could widen a policy the service deliberately narrowed.
    Only a response with no policy at all gets the defaults.
    '''

    if ACCESS_CONTROL_ALLOW_ORIGIN in response.headers:
        return response

    for key, value in DEFAULT_CORS_HEADERS.items():
        response.headers[key] = value

    return response
