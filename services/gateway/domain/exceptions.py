
class RouteNotFoundException(Exception):
    def __init__(self, service, route, *args: object) -> None:
        super().__init__(
            f"No mapping defined for ingress route '{route}' for service '{service}'"
        )
