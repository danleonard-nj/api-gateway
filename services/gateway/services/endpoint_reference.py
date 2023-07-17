

class ServiceEndpointReference:
    def __init__(self):
        self._refs = {}

    def add(
        self,
        service_configuration,
        endpoint_id: str
    ):
        self._refs[endpoint_id] = service_configuration

    def get_service(
        self,
        endpoint_id: str
    ):
        return self._refs.get(endpoint_id)
