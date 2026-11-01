"""Spec 08 H1: the security matrix. One test per rule TESTIGO+ promises,
with the real engine, the real loop and the real `testigo verify`, and no
models (fixture pixel channels). Each class names the rule and where it lives.

  .venv/bin/python -m pytest tests/security
"""

import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

from app.runtime.loop.approval import AutoApprover, DenyApprover
from app.runtime.loop.loop import run as loop_run
from app.common import config
from app.core.decision import events as ev
from app.adapters.meta.channels import FixtureChannel, SamSparkChannel
from app.core.decision.engine import Interceptor
from app.core.policy.model import load as load_policy
from app.core.evidence import keys
from app.core.evidence.bundle import sign_order
from app.security.verifier.verify import verify_receipt
from tests.fixtures import captures as fx
from tests.fixtures.fake_agent import FixtureDriver, ScriptedAgent, run_fixture

CONFIRM = {"kind": "confirm"}


def png(color):
    buf = io.BytesIO()
    Image.new("RGB", (1280, 800), color).save(buf, format="PNG")
    return buf.getvalue()


def policy():
    return load_policy(config.POLICY_PATH)


def check(capture, regions):
    ch = FixtureChannel()
    ch.set_regions(capture.frame, regions)
    return Interceptor(policy(), ch).check(CONFIRM, capture)


class PolicyNotMet(unittest.TestCase):
    """Rule: an order the signed rules do not allow is blocked before the click
    (interceptor/engine.py, interceptor/policy.py)."""

    def test_attackers_address(self):
        d = check(fx.capture_a3(), fx._regions(address=fx.A3))
        self.assertEqual((d.status, d.blocked), (ev.POLICY_VIOLATION, True))

    def test_amount_over_the_maximum(self):
        d = check(fx.capture_clean(), fx._regions(amount="USD 1,600.00"))
        self.assertEqual((d.status, d.blocked), (ev.POLICY_VIOLATION, True))

    def test_buyers_name_with_another_street(self):
        d = check(fx.capture_clean(), fx._regions(address="Larkspur Market · 120 Harbor Road, Unit 5, Riverton"))
        self.assertEqual(d.status, ev.POLICY_VIOLATION)

    def test_loop_never_executes_it(self):
        out = run_fixture("a3", supervised=True)
        self.assertTrue(out.blocked)
        self.assertIsNone(out.order)


class NoReadableEvidence(unittest.TestCase):
    """Rule: without a clear read of the total and the address, nothing is
    allowed (cannot_verify; interceptor/engine.py rule 1)."""

    def test_missing_region(self):
        self.assertEqual(check(fx.capture_clean(), fx._regions(drop="address")).status, ev.CANNOT_VERIFY)

    def test_unsure_region(self):
        self.assertEqual(check(fx.capture_clean(), fx._regions(low={"amount": 0.2})).status, ev.CANNOT_VERIFY)

    def test_two_amounts_on_the_total(self):
        d = check(fx.capture_clean(), fx._regions(amount="USD 1,240.00 USD 88.00"))
        self.assertEqual((d.status, d.blocked), (ev.CANNOT_VERIFY, True))

    def test_nothing_read(self):
        self.assertEqual(check(fx.capture_clean(), []).status, ev.CANNOT_VERIFY)


class ModelFailure(unittest.TestCase):
    """Rule: a model that fails or answers outside its schema never vouches for
    a screen (interceptor/channels.py): cannot_verify."""

    def capture(self):
        c = fx.capture_clean()
        c.screenshot = png((255, 255, 255))
        return c

    def run_with(self, meta):
        return Interceptor(policy(), SamSparkChannel(meta)).check(CONFIRM, self.capture())

    def test_exception(self):
        class Down:
            def chat(self, *a, **k):
                raise TimeoutError("model timed out")

            def segment(self, *a, **k):
                raise TimeoutError("model timed out")
        self.assertEqual(self.run_with(Down()).status, ev.CANNOT_VERIFY)

    def test_off_schema(self):
        from app.adapters.meta.test_channels import FakeMeta
        self.assertEqual(self.run_with(FakeMeta(screen={"lines": [], "amount": "1240"})).status, ev.CANNOT_VERIFY)

    def test_spend_cap(self):
        from app.adapters.meta.client import SpendCapExceeded

        class Broke:
            def chat(self, *a, **k):
                raise SpendCapExceeded("this run spent USD 2.00 of MAX_RUN_SPEND_USD 2.00")

            def segment(self, *a, **k):
                raise SpendCapExceeded("cap")
        self.assertEqual(self.run_with(Broke()).status, ev.CANNOT_VERIFY)


class CodeAndPixelsDiverge(unittest.TestCase):
    """Rule: text in the page code that is not on screen (A1), or on screen and
    not in the code (A2), blocks (interceptor/engine.py, instruction_filter.py)."""

    def test_hidden_in_the_code(self):
        self.assertEqual(check(fx.capture_a1(), fx._regions()).status, ev.DIVERGENCE)
        self.assertTrue(run_fixture("a1").blocked)

    def test_painted_in_the_pixels(self):
        self.assertEqual(check(fx.capture_a2(), fx._regions()).status, ev.DIVERGENCE)
        self.assertTrue(run_fixture("a2").blocked)

    def test_legitimate_hidden_text_is_not_an_attack(self):
        self.assertEqual(check(fx.capture_clean_hidden(), fx._regions()).status, ev.OK)


class SensitiveNeedsThePerson(unittest.TestCase):
    """Rule: a click that confirms an order is never allowed on its own; the
    person approves what the pixels show (interceptor/engine.py, agent/loop.py)."""

    def test_clean_screen_still_asks(self):
        d = check(fx.capture_clean(), fx._regions())
        self.assertTrue(d.needs_approval)
        self.assertFalse(d.allowed_now)
        self.assertEqual(d.approval_event["amount_cents"], 124000)

    def test_denied_means_no_order(self):
        out = run_fixture("clean", approver=DenyApprover())
        self.assertTrue(out.denied)
        self.assertIsNone(out.order)

    def test_every_action_passes_the_hook(self):
        out = run_fixture("clean", approver=AutoApprover())
        self.assertEqual(out.intercepted, out.actions)


class ApprovedThenChanged(unittest.TestCase):
    """Rule: what the person approved is what gets clicked. A change before the
    click blocks (F8 re-read); a change during the check is never clicked
    (spec 07 M3; agent/loop.py)."""

    def driver(self, screens):
        class Changing(FixtureDriver):
            recapture_before_sensitive = True

            def __init__(self):
                super().__init__("clean")
                self.seen = 0

            def observe(self):
                self.seen += 1
                honest = screens(self.seen)
                c = fx.capture_clean(150) if honest else fx.capture_a3(151)
                c.screenshot = png((255, 255, 255) if honest else (90, 90, 90))
                return c

            def pixel_channel(self):
                ch = fx.channel_for("clean")
                ch.set_regions(151, fx._regions(address=fx.A3))
                return ch
        return Changing()

    def run_with(self, screens):
        d = self.driver(screens)
        return loop_run(d, ScriptedAgent(), supervised=True, signing_key=keys.generate_seed()), d

    def test_changed_during_the_check(self):
        out, d = self.run_with(lambda n: n <= 2)
        self.assertTrue(out.blocked)
        self.assertIsNone(d.last_order)

    def test_changed_after_the_click_is_flagged(self):
        out = run_fixture("swap")
        self.assertTrue(out.receipt_flagged)
        self.assertFalse(out.attack_success)


class TamperedEvidence(unittest.TestCase):
    """Rule: anyone can tell an edited receipt from a real one (receipts/verify.py):
    a changed field breaks the signature; a swapped crop or screen breaks its hash."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        c = fx.capture_clean()
        d = Interceptor(policy(), fx.channel_for("clean")).check(CONFIRM, c)
        a = d.approval_event
        after = fx.capture_clean(164)
        receipt, self.path = sign_order(
            policy(), a, {"method": "passkey", "voice_transcript": "", "voice_match": True},
            {n: c.crops[n] for n in ("amount", "address")}, keys.generate_seed(),
            executed_crops={n: after.crops[n] for n in ("amount", "address")},
            executed_read={"amount": "USD 1,240.00", "address": a["address"]},
            run_dir=self.tmp, approved_screen=png((255, 255, 255)), executed_screen=png((250, 250, 250)))
        self.receipt = receipt

    def ok(self):
        return all(c.ok for c in verify_receipt(self.path, evidence_dir=self.tmp).checks)

    def test_the_real_one_verifies_and_signs_screens_and_models(self):
        self.assertTrue(self.ok())
        ev_ = self.receipt["evidence"]
        self.assertEqual(set(ev_["screens"]), {"approved", "executed"})
        self.assertEqual(set(ev_["models"]), {"agent", "reader", "segmenter", "voice"})

    def test_edited_field(self):
        data = json.loads(self.path.read_text())
        data["address"] = data["address"].replace("120 Harbor Road", "88 Mill Street")
        self.path.write_text(json.dumps(data))
        self.assertFalse(self.ok())

    def test_edited_screen_record(self):
        data = json.loads(self.path.read_text())
        data["evidence"]["screens"]["approved"] = "0" * 64
        self.path.write_text(json.dumps(data))
        self.assertFalse(self.ok())

    def test_swapped_crop_file(self):
        (self.tmp / "approved_address.png").write_bytes(b"another crop")
        self.assertFalse(self.ok())

    def test_swapped_screen_file(self):
        (self.tmp / "executed_screen.png").write_bytes(png((0, 0, 0)))
        res = verify_receipt(self.path, evidence_dir=self.tmp)
        self.assertFalse(res.checks[3].ok)
        self.assertIn("executed screen", res.checks[3].detail)

    def test_missing_screen_file(self):
        (self.tmp / "approved_screen.png").unlink()
        self.assertFalse(self.ok())

    def test_receipts_from_before_still_verify(self):
        from tests.fixtures.bundles import build_bundle
        old = self.tmp / "old"
        build_bundle("clean", str(old), seed=keys.generate_seed())
        self.assertNotIn("evidence", json.loads((old / "receipt.json").read_text()))
        self.assertTrue(all(c.ok for c in verify_receipt(old / "receipt.json", evidence_dir=old).checks))


class PolicyNotTrusted(unittest.TestCase):
    """Rule: rules that are edited or not signed by the owner are never used;
    the system fails closed (common/config.py)."""

    def setUp(self):
        from app.core.policy.compile import HEADER, sign_policy_dict, to_yaml
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.seed = keys.generate_seed()
        signed, _ = sign_policy_dict(policy().to_dict() | {"source": "typed"}, self.seed)
        self.path = self.tmp / "active.policy.yaml"
        self.path.write_text(HEADER + to_yaml(signed))
        self.pub = keys.public_from_seed(self.seed)

    def test_signed_is_trusted(self):
        config.trusted_signed_policy(self.path, pubkey=self.pub)

    def test_edited_is_not(self):
        self.path.write_text(self.path.read_text().replace("150000", "9900000"))
        with self.assertRaises(config.PolicyNotTrusted):
            config.trusted_signed_policy(self.path, pubkey=self.pub)

    def test_signed_by_someone_else_is_not(self):
        with self.assertRaises(config.PolicyNotTrusted):
            config.trusted_signed_policy(self.path, pubkey=keys.public_from_seed(keys.generate_seed()))

    def test_an_untrusted_active_policy_is_never_replaced_by_the_committed_one(self):
        runs = self.tmp / "runs"
        with mock.patch.dict(os.environ, {"RUNS_DIR": str(runs),
                                          "SIGNING_KEY_PATH": str(self.tmp / "other.key")}):
            keys.load_or_create_seed(self.tmp / "other.key")
            active = config.active_policy_path()
            active.parent.mkdir(parents=True)
            shutil.copy(self.path, active)
            with self.assertRaises(config.PolicyNotTrusted):
                config.policy_path()


class SpendPerRun(unittest.TestCase):
    """Rule: no single run spends more than MAX_RUN_SPEND_USD (spec 08 H3;
    common/meta_client.py)."""

    def test_the_run_cap_stops_calls_and_resets_per_run(self):
        from types import SimpleNamespace as NS
        from app.adapters.meta.client import MetaClient, SpendCapExceeded
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        s = config.settings()
        from dataclasses import replace
        s = replace(s, max_run_spend_usd=0.01, max_spend_usd=1000.0, meta_base_url="http://x",
                    meta_api_key="k", model_spark="spark-test")
        resp = NS(choices=[NS(message=NS(content="{}"))],
                  usage=NS(prompt_tokens=1_000_000, completion_tokens=0, total_tokens=1_000_000))
        sdk = NS(chat=NS(completions=NS(create=lambda **k: resp)))
        meta = MetaClient(settings=s, usage_path=tmp / "usage.jsonl", sdk_client=sdk)
        meta.chat("spark", [{"role": "user", "content": "x"}])
        self.assertGreater(meta.run_spent_usd(), 0.01)
        with self.assertRaises(SpendCapExceeded):
            meta.chat("spark", [{"role": "user", "content": "x"}])
        meta.start_run()
        meta.chat("spark", [{"role": "user", "content": "x"}])


if __name__ == "__main__":
    unittest.main()
