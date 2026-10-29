"""The interceptor service: the interface (F11) and its event relay.

  make up        # starts this on INTERCEPTOR_PORT, next to the portal

Routes
  /                  the interface (ui/index.html; static files under /ui)
  /status, /health   the F0 status page and its JSON
  POST /events       the loop posts each event here (loopback only)
  POST /events/reset forget the stored events before a new recording
  GET  /events       the stored events, as JSON
  WS   /ws           history first, then every new event
  GET  /api/policy   the signed policy (view 1)
  GET  /api/receipt  the newest receipt.json under runs/, or ?path= (view 7)
  POST /api/verify   runs the real `testigo verify` on that receipt (view 7)
  GET  /api/bench    runs/bench_results.json, or "not available" (view 8)
  GET  /runs/<path>  screenshots and crops (PNG/JPEG only) from runs/

The interface decides nothing and keeps nothing (F11-D4): it shows events and
files. runs/ is git-ignored, so captures exist only on the demo machine.

Who may talk to it: only this machine, and only this page. Every request must
carry a local Host (stops DNS rebinding). Any browser request that sends an
Origin must come from this service's own origin, which keeps other tabs (the
portal included) from injecting events, wiping a run or reading the stream.
Writes also require a JSON body, which makes a cross-site form or no-cors
fetch impossible.
"""

import asyncio
import html
import json
import subprocess
import sys
from pathlib import Path

from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from common import clock, config
from interceptor.hub import PAGE_QUEUE, EventHub, InvalidEvent
from interceptor.policy import load as load_policy

UI_DIR = config.ROOT / "ui"
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}
LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", "testserver"}
VERIFY_TIMEOUT_S = 20

app = FastAPI(title="TESTIGO+ interceptor", docs_url=None, redoc_url=None)
hub = EventHub()


def _hostname(netloc):
    try:
        return (urlsplit("//" + netloc).hostname or "").lower()
    except ValueError:
        return ""


def origin_ok(headers):
    """No Origin (the loop's sink, curl) or exactly this service's origin."""
    origin = headers.get("origin")
    if origin is None:
        return True
    return origin.rstrip("/") in ("http://" + headers.get("host", ""),
                                  "https://" + headers.get("host", ""))


@app.middleware("http")
async def local_page_only(request: Request, call_next):
    if _hostname(request.headers.get("host", "")) not in LOCAL_HOSTS:
        return JSONResponse({"detail": "local host only"}, status_code=403)
    if not origin_ok(request.headers):
        return JSONResponse({"detail": "cross-origin request refused"}, status_code=403)
    return await call_next(request)


# -- helpers ----------------------------------------------------------------

def runs_dir():
    return config.settings().runs_dir.resolve()


def under(base, rel):
    """Resolve `rel` inside `base`, or 404. No `..`, no absolute paths out."""
    base = Path(base).resolve()
    p = (base / str(rel)).resolve()
    if p != base and base not in p.parents:
        raise HTTPException(404, "not found")
    return p


def local_only(request):
    host = request.client.host if request.client else ""
    if host not in LOOPBACK:
        raise HTTPException(403, "loopback only")


def _rel(p):
    try:
        return p.relative_to(config.ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def newest_receipt():
    base = runs_dir()
    found = []
    for p in base.rglob("receipt.json"):
        try:
            real = p.resolve(strict=True)
        except OSError:
            continue                      # broken link
        if base in real.parents and real.is_file():
            found.append((real.stat().st_mtime, real))
    return max(found)[1] if found else None


def receipt_path(path):
    if path:
        p = under(runs_dir(), path)
        if p.name != "receipt.json" or not p.is_file():
            raise HTTPException(404, "receipt not found")
        return p
    p = newest_receipt()
    if p is None:
        raise HTTPException(404, "no receipt under runs/ yet")
    return p


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
        "ui": "/",
        "events_stored": len(hub.history()),
    }


# -- interface --------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse(UI_DIR / "index.html")


app.mount("/ui", StaticFiles(directory=UI_DIR), name="ui")


@app.get("/runs/{path:path}")
def run_file(path):
    p = under(runs_dir(), path)
    kind = IMAGE_TYPES.get(p.suffix.lower())
    if kind is None or not p.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(p, media_type=kind)


# -- events -----------------------------------------------------------------

@app.post("/events")
async def post_event(request: Request):
    local_only(request)
    if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
        raise HTTPException(415, "events must be sent as application/json")
    try:
        event = json.loads(await request.body())
        n = hub.publish(event)
    except (ValueError, InvalidEvent) as e:
        raise HTTPException(422, str(e))
    return {"ok": True, "stored": n}


@app.post("/events/reset")
def reset_events(request: Request):
    local_only(request)
    hub.reset()
    return {"ok": True}


@app.get("/events")
def get_events():
    return hub.history()


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    # Browsers do not apply the same-origin policy to WebSockets, so check here.
    if (_hostname(websocket.headers.get("host", "")) not in LOCAL_HOSTS
            or not origin_ok(websocket.headers)):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue(maxsize=PAGE_QUEUE)
    history = hub.subscribe(loop, queue)
    recv = get = None
    try:
        await websocket.send_json({"type": "hub.history", "events": history})
        recv = asyncio.ensure_future(websocket.receive_text())
        get = asyncio.ensure_future(queue.get())
        while True:
            done, _ = await asyncio.wait({get, recv}, return_when=asyncio.FIRST_COMPLETED)
            if get in done:                   # send first: never drop a dequeued event
                await websocket.send_json(get.result())
                get = asyncio.ensure_future(queue.get())
            if recv in done:
                if recv.exception() is not None:
                    break                     # the page closed
                recv = asyncio.ensure_future(websocket.receive_text())
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(loop, queue)
        for t in (recv, get):
            if t is not None and not t.done():
                t.cancel()


# -- files the views read ---------------------------------------------------

@app.get("/api/policy")
def api_policy():
    s = config.settings()
    policy = load_policy(config.POLICY_PATH)
    sig_valid = None   # unknown without the owner's key on this machine
    if s.signing_key_path.is_file():
        from receipts import keys
        sig_valid = policy.signature_valid(keys.public_from_seed(keys.load_seed(s.signing_key_path)))
    return {
        "owner": policy.owner,
        "source": policy.source,
        "transcript": policy.transcript,
        "pay_only": policy.pay_only,
        "max_per_payment_cop": policy.max_per_payment_cop,
        "ask_before": policy.ask_before,
        "signed_by": policy.signed_by,
        "sha256": policy.sha256(),
        "short_sha": policy.short_sha(),
        "hash_ok": policy.hash_matches_stored(),
        "signed": bool(policy.signature),
        "signature_valid": sig_valid,
    }


@app.get("/api/receipt")
def api_receipt(path: str = ""):
    p = receipt_path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        raise HTTPException(422, "receipt.json is not valid JSON")
    return {"path": p.relative_to(runs_dir()).as_posix(), "receipt": data,
            "modified": p.stat().st_mtime}


@app.post("/api/verify")
def api_verify(request: Request, path: str = ""):
    """Run the real CLI, exactly as anyone would, and return its output."""
    local_only(request)
    p = receipt_path(path)
    cmd = [sys.executable, "-m", "receipts.cli", "verify", str(p)]
    try:
        r = subprocess.run(cmd, cwd=config.ROOT, capture_output=True, text=True,
                           timeout=VERIFY_TIMEOUT_S)
        out, code = r.stdout + r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        out, code = "verify timed out after %ds\n" % VERIFY_TIMEOUT_S, 124
    return {"command": "testigo verify %s" % _rel(p), "output": out, "exit_code": code}


@app.get("/api/bench")
def api_bench():
    p = runs_dir() / "bench_results.json"
    if not p.is_file():
        return {"available": False}
    try:
        return {"available": True, "data": json.loads(p.read_text(encoding="utf-8"))}
    except ValueError:
        return {"available": False, "error": "bench_results.json is not valid JSON"}


# -- F0 status page ---------------------------------------------------------

@app.get("/health")
def health():
    return status()


@app.get("/status", response_class=HTMLResponse)
def status_page():
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
<p class="muted">Interface: <a href="/">/</a> &middot; events stored: {n} &middot;
Health JSON: <a href="/health">/health</a></p>
</body></html>""".format(
        time=html.escape(st["time"]), portal=html.escape(st["portal"]),
        sha=html.escape(st["policy_sha256"]), hok="ok" if st["policy_hash_ok"] else "MISMATCH",
        key="present" if st["signing_key_present"] else "missing (run: testigo keygen)",
        rows=rows, n=st["events_stored"])
