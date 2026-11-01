"""TESTIGO+ as an MCP server over stdio (spec 07 M9), standard library only.

    .venv/bin/python -m app.runtime.mcp

Any computer-use agent that speaks MCP can call TESTIGO+ before a sensitive
click. Three tools:

  testigo_check_screen    the screenshot at the click + the page code's text
                          -> ok (with what the person must approve),
                             divergence, policy_violation or cannot_verify
  testigo_verify_receipt  `testigo verify` on a receipt under runs/
  testigo_policy          the signed rules in force

Messages are JSON-RPC 2.0, one per line on stdin/stdout (MCP stdio transport).
Logs go to stderr only. The check uses Meta's real models (Spark + SAM 3.1),
the keys in .env and the spend cap, like every other real run.
"""

import base64
import binascii
import json
import sys

from app.common import config

PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "testigo", "version": "0.1.0"}

TOOLS = [
    {
        "name": "testigo_check_screen",
        "description": (
            "Call before clicking a button that confirms an order. Reads the screenshot "
            "with Meta's Spark and SAM 3.1, compares it with the page code's text and the "
            "owner's signed rules. Anything but status 'ok' means: do not click. With 'ok', "
            "show the person `approve` (total and ship-to as read from the pixels) and click "
            "only if they approve."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "screenshot_png_base64": {"type": "string",
                                          "description": "PNG of the screen, taken right before the click"},
                "page_text": {"type": "string",
                              "description": "All text in the page code, rendered or not "
                                             "(e.g. document.body.textContent), one item per line"},
            },
            "required": ["screenshot_png_base64", "page_text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "testigo_verify_receipt",
        "description": "Run `testigo verify` on a signed receipt (a receipt.json under runs/).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string",
                                    "description": "receipt.json, relative to runs/"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "testigo_policy",
        "description": "The owner's signed rules in force: where orders may ship and the maximum per order.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]

MAX_PNG_BYTES = 12 * 1024 * 1024


class ToolError(Exception):
    """A bad argument or a refused call: returned as a tool result with isError."""


def tool_check_screen(args, check=None):
    raw = args.get("screenshot_png_base64")
    text = args.get("page_text")
    if not isinstance(raw, str) or not raw or not isinstance(text, str):
        raise ToolError("screenshot_png_base64 and page_text are required strings")
    try:
        png = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError):
        raise ToolError("screenshot_png_base64 is not valid base64")
    if len(png) > MAX_PNG_BYTES or not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ToolError("the screenshot must be a PNG under %d MB" % (MAX_PNG_BYTES // (1024 * 1024)))
    if check is None:
        from app.core.decision.guard import check_screen as check
    return check(png, text)


def tool_verify_receipt(args):
    rel = args.get("path")
    if not isinstance(rel, str) or not rel:
        raise ToolError("path is required")
    base = config.settings().runs_dir.resolve()
    p = (base / rel).resolve()
    if base not in p.parents or p.name != "receipt.json" or not p.is_file():
        raise ToolError("no receipt.json at runs/%s" % rel)
    from app.security.verifier.cli import run_verify
    out, code = run_verify(p)
    return {"valid": code == 0, "output": out}


def tool_policy(_args):
    from app.core.decision.guard import policy_summary
    return policy_summary()


HANDLERS = {"testigo_check_screen": tool_check_screen,
            "testigo_verify_receipt": tool_verify_receipt,
            "testigo_policy": tool_policy}


def handle(msg, handlers=HANDLERS):
    """One JSON-RPC message -> the response dict, or None for a notification."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "invalid request")
    method, mid = msg["method"], msg.get("id")
    if "id" not in msg:                     # a notification: never answered
        return None
    params = msg.get("params") or {}
    if method == "initialize":
        asked = params.get("protocolVersion") if isinstance(params, dict) else None
        return _result(mid, {"protocolVersion": asked if isinstance(asked, str) else PROTOCOL_VERSION,
                             "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO,
                             "instructions": "Call testigo_check_screen before any click that confirms "
                                             "an order; click only on status ok and after the person approves."})
    if method == "ping":
        return _result(mid, {})
    if method == "tools/list":
        return _result(mid, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name") if isinstance(params, dict) else None
        if name not in handlers:
            return _error(mid, -32602, "unknown tool: %s" % name)
        args = params.get("arguments") or {}
        if not isinstance(args, dict):
            return _error(mid, -32602, "arguments must be an object")
        try:
            out = handlers[name](args)
        except ToolError as e:
            return _result(mid, _content({"error": str(e)}, is_error=True))
        except Exception as e:  # noqa: BLE001 - a failed check never reads as "ok"
            return _result(mid, _content({"error": "%s: %s" % (type(e).__name__, str(e)[:300])},
                                         is_error=True))
        return _result(mid, _content(out))
    return _error(mid, -32601, "method not found: %s" % method)


def _content(obj, is_error=False):
    return {"content": [{"type": "text", "text": json.dumps(obj, ensure_ascii=False, indent=2)}],
            "structuredContent": obj, "isError": is_error}


def _result(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def serve(stdin=sys.stdin, stdout=sys.stdout, handlers=HANDLERS):
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            reply = _error(None, -32700, "parse error")
        else:
            reply = handle(msg, handlers)
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            stdout.flush()


def main():
    print("testigo MCP server on stdio (simulation only)", file=sys.stderr)
    serve()
    return 0
