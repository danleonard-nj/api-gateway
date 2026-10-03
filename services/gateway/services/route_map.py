import uuid
from typing import Any, Callable


class RouteMap:
    def __init__(self, route: dict):
        self.route = route
        self.endpoint_id = str(uuid.uuid4())

        self.service_endpoint = route.get('service_endpoint')
        self.gateway_endpoint = route.get('gateway_endpoint')
        self.allowed_methods = self.route.get('allowed_methods') or []

        # Per-route streaming override.  None means inherit the service-wide
        # setting; True forwards the upstream response body as it arrives
        # instead of buffering it.
        self.streaming = self.route.get('streaming')
        self.stream_read_timeout = self.route.get('stream_read_timeout')

    def map_route(
        self,
        app: Any,
        proxy_request: Callable
    ):
        '''
        Map a proxy route to the gateway server
        as a route rule
        '''

        # OPTIONS is forwarded upstream rather than answered here.  The
        # gateway does not enforce CORS -- it passes the service's own policy
        # through -- and Quart's automatic OPTIONS handling would otherwise
        # short-circuit every preflight with a response the service never saw.
        methods = list(self.allowed_methods)
        if 'OPTIONS' not in {method.upper() for method in methods}:
            methods.append('OPTIONS')

        app.add_url_rule(
            rule=self.gateway_endpoint,
            endpoint=self.endpoint_id,
            methods=methods,
            provide_automatic_options=False)

        app.view_functions[self.endpoint_id] = proxy_request
