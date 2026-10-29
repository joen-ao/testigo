"""F11: the service relays events to the interface and serves only what it should.

Test data only: example events and the synthetic receipts in examples/. The
interface itself is static; these tests cover what feeds it.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient

from common.config import ROOT
from interceptor import events as ev
from interceptor import service
from interceptor.hub import EventHub, InvalidEvent, validate


def check_event():
    return ev.check_result(7, ev.DIVERGENCE,
                           [ev.region("amount", (812, 640, 1010, 690), "COP 120,000", 0.97)],
                           [], ["a line painted in the banner"], 1400, "visible text not in code")


class HubTests(unittest.TestCase):
    def test_validate_accepts_contract_and_rejects_the_rest(self):
        e = check_event()
        self.assertIs(validate(e), e)
        for bad in ([], "x", {"type": "nope"}, {"no": "type"},
                    {"type": "agent.step", "label": "x" * 70_000}):
            with self.assertRaises(InvalidEvent):
                validate(bad)

    def test_history_is_capped_and_reset(self):
        hub = EventHub(maxlen=3)
        for i in range(5):
            hub.publish(ev.agent_step(i, "step %d" % i))
        self.assertEqual([e["frame"] for e in hub.history()], [2, 3, 4])
        hub.reset()
        self.assertEqual(hub.history(), [])


class ServiceUITests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.env = mock.patch.dict(os.environ, {"RUNS_DIR": str(self.tmp)})
        self.env.start()
        service.hub.reset()
        self.c = TestClient(service.app)

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)
        service.hub.reset()

    def test_root_serves_the_interface_and_status_moved(self):
        r = self.c.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn('/ui/app.js', r.text)
        self.assertEqual(self.c.get("/ui/app.css").status_code, 200)
        self.assertIn("TESTIGO+ interceptor", self.c.get("/status").text)

    def test_post_then_history(self):
        r = self.c.post("/events", json=check_event())
        self.assertEqual(r.status_code, 200)
        got = self.c.get("/events").json()
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["regions"][0]["box"], [812, 640, 1010, 690])

    def test_invalid_event_is_refused(self):
        self.assertEqual(self.c.post("/events", json={"type": "nope"}).status_code, 422)
        self.assertEqual(self.c.post("/events", content=b"not json",
                                     headers={"Content-Type": "application/json"}).status_code, 422)
        # shapes the views rely on are checked, so one bad event cannot break a page
        bad = [ev.run_started("__proto__", "a1"),
               {"type": "approval.requested", "amount_cop": 1, "recipient": "x"},
               dict(check_event(), regions=[{"label": "amount"}]),
               dict(ev.payment_executed(1, "x", 1), amount_cop=True)]
        for e in bad:
            self.assertEqual(self.c.post("/events", json=e).status_code, 422, e)
        self.assertEqual(self.c.get("/events").json(), [])

    def test_other_pages_cannot_inject_wipe_or_listen(self):
        """A tab on another origin (the portal, any site) is refused; so is a
        non-JSON body, which is what a no-cors fetch would have to send."""
        evil = {"Origin": "http://evil.example"}
        self.assertEqual(self.c.post("/events", json=check_event(), headers=evil).status_code, 403)
        self.assertEqual(self.c.post("/events", content=b'{"type":"agent.step","label":"x"}',
                                     headers={"Content-Type": "text/plain"}).status_code, 415)
        self.c.post("/events", json=ev.agent_step(1, "kept"))
        self.assertEqual(self.c.post("/events/reset", headers=evil).status_code, 403)
        self.assertEqual(self.c.get("/events", headers=evil).status_code, 403)
        self.assertEqual(len(self.c.get("/events").json()), 1)
        # the portal runs on another port: a different origin too
        portal = {"Origin": "http://localhost:8080"}
        self.assertEqual(self.c.post("/events", json=check_event(), headers=portal).status_code, 403)
        # the interface itself (same origin) may run verify and reset
        same = {"Origin": "http://testserver"}
        self.assertEqual(self.c.post("/events/reset", headers=same).status_code, 200)
        # DNS rebinding: a foreign Host is refused everywhere
        self.assertEqual(self.c.get("/events", headers={"Host": "rebind.example"}).status_code, 403)
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises(WebSocketDisconnect):
            with self.c.websocket_connect("/ws", headers=evil) as ws:
                ws.receive_json()

    def test_websocket_replays_history_then_streams(self):
        self.c.post("/events", json=ev.run_started("supervised", "a1"))
        with self.c.websocket_connect("/ws") as ws:
            first = ws.receive_json()
            self.assertEqual(first["type"], "hub.history")
            self.assertEqual([e["type"] for e in first["events"]], ["run.started"])
            self.c.post("/events", json=check_event())
            live = ws.receive_json()
            self.assertEqual(live["type"], "check.result")
            self.c.post("/events/reset")
            self.assertEqual(ws.receive_json()["type"], "hub.reset")

    def test_runs_serves_images_only_and_never_escapes(self):
        (self.tmp / "r1").mkdir()
        (self.tmp / "r1" / "frame-1.png").write_bytes(b"\x89PNG fake")
        (self.tmp / "usage.jsonl").write_text("{}")
        self.assertEqual(self.c.get("/runs/r1/frame-1.png").status_code, 200)
        self.assertEqual(self.c.get("/runs/usage.jsonl").status_code, 404)
        self.assertEqual(self.c.get("/runs/../pyproject.toml").status_code, 404)
        self.assertEqual(self.c.get("/runs/%2e%2e/.secrets/receipts.key").status_code, 404)

    def test_policy_for_view_1(self):
        p = self.c.get("/api/policy").json()
        self.assertTrue(p["hash_ok"])
        self.assertEqual(p["pay_only"][0]["account"], "310-XXX-4417")
        self.assertEqual(p["max_per_payment_cop"], 150000)

    def test_bench_absent_says_so(self):
        self.assertEqual(self.c.get("/api/bench").json(), {"available": False})

    def test_newest_receipt_ignores_links_out_of_runs(self):
        outside = Path(tempfile.mkdtemp())
        try:
            (outside / "receipt.json").write_text('{"id": "outside"}')
            (self.tmp / "x").mkdir()
            (self.tmp / "x" / "receipt.json").symlink_to(outside / "receipt.json")
            (self.tmp / "y").mkdir()
            (self.tmp / "y" / "receipt.json").symlink_to(self.tmp / "missing.json")
            self.assertEqual(self.c.get("/api/receipt").status_code, 404)
            (self.tmp / "z").mkdir()
            (self.tmp / "z" / "receipt.json").write_text("not json")
            self.assertEqual(self.c.get("/api/receipt").status_code, 422)
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_receipt_and_real_verify(self):
        self.assertEqual(self.c.get("/api/receipt").status_code, 404)
        for name in ("clean", "a3"):
            shutil.copytree(ROOT / "examples" / name, self.tmp / name)
        os.utime(self.tmp / "a3" / "receipt.json", (2_000_000_000, 2_000_000_000))
        newest = self.c.get("/api/receipt").json()
        self.assertEqual(newest["path"], "a3/receipt.json")

        ok = self.c.post("/api/verify?path=clean/receipt.json").json()
        self.assertEqual(ok["exit_code"], 0, ok["output"])
        self.assertIn("Signature valid — evidence hashes match", ok["output"])
        bad = self.c.post("/api/verify?path=a3/receipt.json").json()
        self.assertEqual(bad["exit_code"], 1)
        self.assertIn("Evidence mismatch at step 4", bad["output"])

        self.assertEqual(self.c.get("/api/receipt?path=../examples/clean/receipt.json").status_code, 404)
        self.assertEqual(self.c.post("/api/verify?path=clean/approved_amount.png").status_code, 404)


if __name__ == "__main__":
    unittest.main()
