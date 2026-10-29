"""The interceptor service (F0 shell).

For now it serves a status page and a health check. The event WebSocket and
the interface (F11) are added here by their specs.

  make up        # starts this on INTERCEPTOR_PORT, next to the portal
"""

import html

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from common import clock, config
from interceptor.policy import load as load_policy

app = FastAPI(title="TESTIGO+ interceptor", docs_url=None, redoc_url=None)


def status():
    s = config.settings()
    try:
        policy = load_policy(config.POLICY_PATH)
        policy_sha = policy.short_sha()
        policy_ok = policy.hash_matches_stored()
    except Exception as e:  # noqa: BLE001
        policy_sha, policy_ok = "unreadable (%s)" % type(e).__name__, False
    return {
        "service": "interceptor",
        "time": clock.iso(),
        "portal": s.portal_url,
        "policy_sha256": policy_sha,
        "policy_hash_ok": policy_ok,
        "models_configured": config.configured(),
        "signing_key_present": s.signing_key_path.is_file(),
        "ui": "not built yet (F11)",
    }


@app.get("/health")
def health():
    return status()


@app.get("/", response_class=HTMLResponse)
def index():
    st = status()
    rows = "".join(
        "<tr><td>%s</td><td>%s</td></tr>" % (html.escape(k), "set" if v else "<b>empty</b>")
        for k, v in st["models_configured"].items())
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>TESTIGO+ interceptor</title>
<style>body{{font-family:system-ui,sans-serif;background:#FAFAF8;color:#0B0B0B;margin:40px;max-width:720px}}
h1{{color:#104281;font-size:22px}} td{{padding:4px 16px 4px 0}} .muted{{color:#52514E;font-size:14px}}</style>
</head><body>
<h1>TESTIGO+ interceptor &middot; running</h1>
<p class="muted">Simulation only: no real money, no real accounts. {time}</p>
<p>Portal: <a href="{portal}/orders/new?scenario=clean">{portal}</a></p>
<p>Policy: {sha} &middot; hash {hok}</p>
<p>Signing key: {key}</p>
<h2 style="font-size:16px">Meta API configuration</h2>
<table>{rows}</table>
<p class="muted">The live interface arrives with F11. Health JSON: <a href="/health">/health</a></p>
</body></html>""".format(
        time=html.escape(st["time"]), portal=html.escape(st["portal"]),
        sha=html.escape(st["policy_sha256"]), hok="ok" if st["policy_hash_ok"] else "MISMATCH",
        key="present" if st["signing_key_present"] else "missing (run: testigo keygen)",
        rows=rows)
