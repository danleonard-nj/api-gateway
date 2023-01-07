import uuid
from typing import Any, Callable


class RouteMap:
    def __init__(self, route: dict):
        self.route = route
        self.endpoint_id = str(uuid.uuid4())

        self.service_endpoint = route.get('service_endpoint')
        self.gateway_endpoint = route.get('gateway_endpoint')
        self.allowed_methods = self.route.get('allowed_methods') or []

    def map_route(
        self,
        app: Any,
        proxy_request: Callable
    ):
        '''
        Map a proxy route to the gateway server
        as a route rule
        '''

        app.add_url_rule(
            rule=self.gateway_endpoint,
            endpoint=self.endpoint_id,
            methods=self.allowed_methods)

        app.view_functions[self.endpoint_id] = proxy_request
