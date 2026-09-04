
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

        self.base_url = service.get('base_url')
        self.port = self.service.get('port')
        self.cors = self.service.get('cors')
        self.routing = self.service.get('routing')

        # Service-wide default for response streaming.  Individual routes may
        # override it.  Off by default so existing services are unaffected.
        self.streaming = bool(self.service.get('streaming', False))

        # Read timeout applied to streaming routes, in seconds.  None means no
        # read timeout, which is what a long-lived SSE response needs -- the
        # client's default 120s read timeout would otherwise kill the stream
        # during any gap between events.
        self.stream_read_timeout = self.service.get('stream_read_timeout')
