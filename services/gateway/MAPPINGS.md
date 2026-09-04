# Gateway route mappings

Every `*.json` in this directory is loaded at startup by
`ApiGateway._gather_route_configs`, which does `os.listdir('mapping')`. Dropping
a file in is the whole registration — nothing else references it by name.

## Shape

```json
{
  "services": {
    "my_service_api": {
      "base_url": "http://my-service.my-namespace.svc.cluster.local",
      "port": 80,
      "routing": [
        {
          "gateway_endpoint": "/api/mine/thing",
          "service_endpoint": "/thing",
          "allowed_methods": ["GET", "POST"]
        }
      ]
    }
  }
}
```

Service keys are merged across files (`configs |= config`), so a duplicate
service key in two files silently wins by load order. Keep them unique.

Route params use Werkzeug syntax and must appear in both endpoints:
`"/api/mine/thing/<thing_id>"` → `"/thing/<thing_id>"`.

## Streaming routes

By default the proxy buffers: it awaits the entire upstream response and
returns `response.content`. That is right for JSON APIs and wrong for anything
that produces output over time — server-sent events, MCP Streamable HTTP, chunked
downloads, long-running progress output. Buffering delays the first byte until
the last one arrives, and the client's 120s read timeout applies to the whole
call.

Set `"streaming": true` on the route to forward the response body as it
arrives:

```json
{
  "gateway_endpoint": "/api/oura/mcp",
  "service_endpoint": "/mcp",
  "allowed_methods": ["GET", "POST", "DELETE"],
  "streaming": true,
  "stream_read_timeout": null
}
```

`"streaming": true` can also go at the service level to apply to every route in
that service; a route-level value overrides it. Both default to off, so an
existing mapping that says nothing keeps its exact current behaviour.

`stream_read_timeout` is seconds, and `null` means no read timeout — the right
default for an SSE stream that is idle between events. Omit it to inherit the
service value; omit both and it is `null`.

### What changes on a streaming route

The request body is still read in full before forwarding. Only the *response*
streams. Streaming the request too would mean handling `Expect: 100-continue`
and non-idempotent retries, and nothing routed here sends a large body.

Header handling is stricter than on the buffered path, because it has to be:

- **Hop-by-hop headers are dropped** in both directions (`connection`,
  `keep-alive`, `te`, `trailer`, `transfer-encoding`, `upgrade`,
  `proxy-authenticate`, `proxy-authorization`). They describe a socket that
  ends at the gateway.
- **`Content-Length` is dropped** from the response — the body is re-chunked as
  it streams, so an upstream length would contradict what we actually send.
- **`Date` and `Server` are dropped** from the response; our own ASGI server
  emits them, and forwarding the upstream's yields a comma-joined duplicate.
- **`Host` is rewritten** to the upstream, which is what a service doing Host
  validation expects. The original goes out as `X-Forwarded-Host`, alongside
  `X-Forwarded-For` and `X-Forwarded-Proto`.

Everything else — `Authorization` included — is forwarded unchanged, so
upstream auth still applies end to end.

### Caveat

Once the response head is sent, a mid-stream upstream failure cannot become a
5xx. The proxy logs it and ends the stream, leaving the client with a truncated
body. That is unavoidable for any streaming proxy; the alternative is
buffering, which is the thing being avoided.

### Ingress

A streaming route is only as good as the proxy in front of the gateway. On
ingress-nginx that means:

```yaml
nginx.ingress.kubernetes.io/proxy-buffering: "off"
nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
```

Without those, nginx re-buffers what the gateway just went to the trouble of
streaming.
