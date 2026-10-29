"""Where the loop's events go besides `Outcome.events` (F11).

The loop hands every event to a sink. `HttpSink` posts it to the interceptor
service, which relays it to the interface over WebSocket.

Publishing is best effort by design: the interface only shows, it never
decides, so a service that is down or slow must not change a verdict or stop a
run. A failed post is counted and the run goes on.
"""

import json
import urllib.request

from common import config


class Sink:
    def publish(self, event):                 # pragma: no cover - interface
        raise NotImplementedError


class NullSink(Sink):
    def publish(self, event):
        return True


class HttpSink(Sink):
    """Posts JSON (the content type the service requires). Ignores HTTP(S)_PROXY:
    the service is local, and a proxy would silently swallow the events."""

    def __init__(self, url, timeout=0.5):
        self.url = url
        self.timeout = timeout
        self.failures = 0
        self._open = urllib.request.build_opener(urllib.request.ProxyHandler({})).open

    def publish(self, event):
        body = json.dumps(event, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with self._open(req, timeout=self.timeout) as r:
                return 200 <= r.status < 300
        except Exception:  # noqa: BLE001 - never let the interface stop a run
            self.failures += 1
            return False


def service_url(path=""):
    s = config.settings()
    host = s.interceptor_host
    if host in ("0.0.0.0", "::", ""):
        host = "127.0.0.1"
    return "http://%s:%d%s" % (host, s.interceptor_port, path)


def default_sink():
    """The sink a real run uses: the local interceptor service."""
    return HttpSink(service_url("/events"))
