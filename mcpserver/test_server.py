"""Spec 07 M9: the MCP server's protocol, with the check replaced (no models)."""

import base64
import io
import json
import unittest

from mcpserver import server

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16


def call(name, arguments, handlers=None, mid=3):
    return server.handle({"jsonrpc": "2.0", "id": mid, "method": "tools/call",
                          "params": {"name": name, "arguments": arguments}},
                         handlers or server.HANDLERS)


class ProtocolTests(unittest.TestCase):
    def test_initialize_list_and_notifications(self):
        r = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                           "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                      "clientInfo": {"name": "t", "version": "0"}}})
        self.assertEqual(r["result"]["protocolVersion"], "2025-03-26")
        self.assertIn("tools", r["result"]["capabilities"])
        self.assertIsNone(server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        names = [t["name"] for t in server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]]
        self.assertEqual(names, ["testigo_check_screen", "testigo_verify_receipt", "testigo_policy"])

    def test_errors(self):
        self.assertEqual(server.handle({"jsonrpc": "2.0", "id": 9, "method": "nope"})["error"]["code"], -32601)
        self.assertEqual(server.handle({"id": 9, "method": "ping"})["error"]["code"], -32600)
        self.assertEqual(call("nope", {})["error"]["code"], -32602)

    def test_check_screen_passes_the_png_and_text(self):
        seen = {}

        def fake(args):
            return server.tool_check_screen(args, check=lambda png, text: seen.update(png=png, text=text)
                                            or {"status": "ok", "needs_approval": True})
        r = call("testigo_check_screen", {"screenshot_png_base64": base64.b64encode(PNG).decode(),
                                          "page_text": "Ship to\n120 Harbor Road"},
                 handlers={"testigo_check_screen": fake})
        self.assertFalse(r["result"]["isError"])
        self.assertEqual(r["result"]["structuredContent"]["status"], "ok")
        self.assertEqual(seen, {"png": PNG, "text": "Ship to\n120 Harbor Road"})
        self.assertEqual(json.loads(r["result"]["content"][0]["text"])["status"], "ok")

    def test_check_screen_refuses_bad_input_as_a_tool_error(self):
        for args in ({"screenshot_png_base64": "!!", "page_text": ""},
                     {"screenshot_png_base64": base64.b64encode(b"GIF89a").decode(), "page_text": ""},
                     {"page_text": "x"}):
            r = call("testigo_check_screen", args)
            self.assertTrue(r["result"]["isError"], args)

    def test_a_failing_check_is_an_error_never_ok(self):
        def boom(args):
            raise RuntimeError("spend cap")
        r = call("testigo_check_screen", {}, handlers={"testigo_check_screen": boom})
        self.assertTrue(r["result"]["isError"])
        self.assertIn("spend cap", r["result"]["structuredContent"]["error"])

    def test_verify_receipt_stays_under_runs(self):
        r = call("testigo_verify_receipt", {"path": "../../etc/passwd"})
        self.assertTrue(r["result"]["isError"])

    def test_policy(self):
        r = call("testigo_policy", {})
        self.assertEqual(r["result"]["structuredContent"]["ship_only_to"][0]["name"], "Larkspur Market")

    def test_serve_reads_lines_and_answers_requests_only(self):
        lines = "\n".join([json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
                           json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                           "not json", ""]) + "\n"
        out = io.StringIO()
        server.serve(io.StringIO(lines), out)
        replies = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual([r.get("id") for r in replies], [1, None])
        self.assertEqual(replies[1]["error"]["code"], -32700)


if __name__ == "__main__":
    unittest.main()
