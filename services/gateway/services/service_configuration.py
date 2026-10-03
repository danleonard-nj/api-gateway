# NOTE: CORS is not configured per service.  An upstream that sets its own
# Access-Control-* headers has them passed through untouched; one that sets
# none gets the gateway's open default (utilities/cors.py).  OPTIONS
# preflights are forwarded so a service with a policy answers them itself.

class ServiceConfiguration:
    def __init__(self, service: dict, name: str):
        self.service = service
        self.name = name

        self.base_url = service.get('base_url')
        self.port = self.service.get('port')
        self.routing = self.service.get('routing')

        # Service-wide default for response streaming.  Individual routes may
        # override it.  Off by default so existing services are unaffected.
        self.streaming = bool(self.service.get('streaming', False))

        # Read timeout applied to streaming routes, in seconds.  None means no
        # read timeout, which is what a long-lived SSE response needs -- the
        # client's default 120s read timeout would otherwise kill the stream
        # during any gap between events.
        self.stream_read_timeout = self.service.get('stream_read_timeout')
