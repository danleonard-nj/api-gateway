from ctypes import Union
from typing import Any, Callable
import uuid


class RouteMap:
    def __init__(self, route: dict):
        self.route = route
        self.endpoint_id = str(uuid.uuid4())

    @property
    def service_endpoint(self):
        return self.route.get('service_endpoint')

    @property
    def gateway_endpoint(self):
        return self.route.get('gateway_endpoint')

    @property
    def allowed_methods(self):
        methods = self.route.get('allowed_methods') or []
        return methods

    def map_route(
        self,
        app: Any,
        proxy_request: Callable
    ):
        '''
        Map a proxy route to the gateway server
        as a route rule

        Args:
            app (_type_): gateway server app
            proxy_request (_type_): the view
            function to map to the endpoin
        '''

        app.add_url_rule(
            rule=self.gateway_endpoint,
            endpoint=self.endpoint_id,
            methods=self.allowed_methods)

        app.view_functions[self.endpoint_id] = proxy_request
