"""F0 §8 and §15: the Meta client against a fake local server (no real API).

Covers: usage log, cost estimate, spend cap, retries only on retryable errors,
and refusing to run without configuration.
"""

import dataclasses
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from common import config
from common.meta_client import MetaClient, NotConfigured, SpendCapExceeded

COMPLETION = {
    "id": "c1", "object": "chat.completion", "created": 0, "model": "fake",
    "choices": [{"index": 0, "finish_reason": "stop",
                 "message": {"role": "assistant", "content": "ok"}}],
    "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0, "total_tokens": 1_000_000},
}


class FakeAPI(BaseHTTPRequestHandler):
    script = []   # statuses to return, in order; then 200
    calls = 0

    def do_POST(self):
        FakeAPI.calls += 1
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        status = FakeAPI.script.pop(0) if FakeAPI.script else 200
        body = json.dumps(COMPLETION if status == 200 else {"error": {"message": "x"}}).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class MetaClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeAPI)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d/v1" % cls.httpd.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def setUp(self):
        FakeAPI.script, FakeAPI.calls = [], 0
        self.tmp = tempfile.mkdtemp()
        self.usage = Path(self.tmp, "usage.jsonl")

    def client(self, max_spend=10.0, **over):
        fields = dict(meta_base_url=self.base, meta_api_key="test-not-a-real-key",
                      model_spark="fake-spark", max_spend_usd=max_spend)
        fields.update(over)
        s = dataclasses.replace(config.settings(), **fields)
        return MetaClient(settings=s, usage_path=self.usage, sleep=lambda _: None)

    def records(self):
        return [json.loads(x) for x in self.usage.read_text().splitlines()]

    def test_call_is_logged_with_cost(self):
        resp, ms = self.client().chat("spark", [{"role": "user", "content": "hi"}])
        self.assertEqual(resp.choices[0].message.content, "ok")
        rec = self.records()[-1]
        self.assertTrue(rec["ok"])
        self.assertEqual(rec["tool"], "spark")
        self.assertEqual(rec["model"], "fake-spark")
        self.assertAlmostEqual(rec["cost_usd"], 1.25)   # 1M input tokens at USD 1.25
        self.assertGreaterEqual(rec["latency_ms"], 0)

    def test_spend_cap_stops_calls(self):
        c = self.client(max_spend=1.0)
        c.chat("spark", [{"role": "user", "content": "hi"}])   # spends 1.25
        with self.assertRaises(SpendCapExceeded):
            c.chat("spark", [{"role": "user", "content": "hi"}])
        self.assertEqual(FakeAPI.calls, 1)

    def test_retries_rate_limit_then_succeeds(self):
        FakeAPI.script = [429]
        self.client().chat("spark", [{"role": "user", "content": "hi"}])
        recs = self.records()
        self.assertEqual([r["ok"] for r in recs], [False, True])
        self.assertEqual(FakeAPI.calls, 2)

    def test_gives_up_after_two_retries(self):
        FakeAPI.script = [429, 429, 429]
        with self.assertRaises(Exception):
            self.client().chat("spark", [{"role": "user", "content": "hi"}])
        self.assertEqual(FakeAPI.calls, 3)

    def test_no_retry_on_bad_request(self):
        FakeAPI.script = [400]
        with self.assertRaises(Exception):
            self.client().chat("spark", [{"role": "user", "content": "hi"}])
        self.assertEqual(FakeAPI.calls, 1)

    def test_refuses_without_configuration(self):
        with self.assertRaises(NotConfigured):
            self.client(meta_base_url="").chat("spark", [{"role": "user", "content": "hi"}])
        with self.assertRaises(NotConfigured):
            self.client(model_spark="").chat("spark", [{"role": "user", "content": "hi"}])

    def test_sam_refuses_until_endpoint_known(self):
        with self.assertRaises(NotConfigured):
            self.client().segment(b"png", "pay button")


if __name__ == "__main__":
    unittest.main()
