
class ServiceCors:
    def __init__(self, cors: dict):
        self._cors = cors or {}

    @property
    def access_control_allow_origins(self):
        if not self._cors:
            return '*'
        return self._cors.get('origins')

    @property
    def access_control_allow_headers(self):
        if not self._cors:
            return '*'
        return self._cors.get('headers')

    @property
    def access_control_allow_methods(self):
        if not self._cors:
            return '*'
        return self._cors.get('methods')

    def get_headers(self):
        _headers = {}
        _headers['Access-Control-Allow-Origin'] = self.access_control_allow_origins
        _headers['Access-Control-Allow-Headers'] = self.access_control_allow_headers
        _headers['Access-Control-Allow-Methods'] = self.access_control_allow_methods
        return _headers


class ServiceConfiguration:
    def __init__(self, service: dict, name: str):
        self.service = service
        self.name = name

    @property
    def base_url(self):
        _base_url = self.service.get('base_url')
        return _base_url

    @property
    def port(self):
        _port = self.service.get('port')
        return _port

    @property
    def cors(self):
        _cors = self.service.get('cors')
        return ServiceCors(cors=_cors)

    @property
    def routing(self):
        _routing = self.service.get('routing')
        return _routing

    @routing.setter
    def routing(self):
        raise NotImplementedError()

    @port.setter
    def port(self):
        raise NotImplementedError()

    @base_url.setter
    def base_url(self):
        raise NotImplementedError()
