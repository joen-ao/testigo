"""Tests for receipts: Ed25519, signing, and the four verify checks.

  make test   (or: .venv/bin/python -m pytest receipts)
"""

import json
import tempfile
import unittest
from pathlib import Path

from common.config import POLICY_PATH
from interceptor.policy import load as load_policy
from tests.fixtures.bundles import build_bundle

from . import keys
from .receipt import build, canonical, verify_signature
from .verify import verify_receipt

POLICY = str(POLICY_PATH)


class Ed25519Tests(unittest.TestCase):
    def test_sign_verify_roundtrip(self):
        seed = keys.generate_seed()
        pub = keys.public_from_seed(seed)
        sig = keys.sign(seed, b"evidence")
        self.assertTrue(keys.verify(pub, b"evidence", sig))
        self.assertFalse(keys.verify(pub, b"evidence!", sig))
        self.assertEqual(len(pub), 32)
        self.assertEqual(len(sig), 64)

    def test_wrong_key_fails(self):
        seed = keys.generate_seed()
        other = keys.public_from_seed(keys.generate_seed())
        sig = keys.sign(seed, b"x")
        self.assertFalse(keys.verify(other, b"x", sig))


class SignBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy(POLICY)
        cls.seed = keys.generate_seed()

    def _receipt(self, executed=None):
        approved = {"amount": b"A", "recipient": b"R"}
        executed = executed or {"amount": b"A", "recipient": b"R"}
        return build(self.policy, "pay 120000 COP -> Distribuidora X",
                     120000, "Distribuidora X · 310-XXX-4417",
                     approved, executed,
                     {"method": "passkey", "voice_transcript": "..."}, self.seed)

    def test_signature_valid_and_covers_body(self):
        r = self._receipt()
        self.assertTrue(verify_signature(r))
        r2 = dict(r)
        r2["amount_cop"] = 999999        # change a signed field
        self.assertFalse(verify_signature(r2))

    def test_canonical_excludes_signature(self):
        r = self._receipt()
        self.assertNotIn(b"signature", canonical(r))

    def test_pinned_pubkey_matches(self):
        r = self._receipt()
        pub = keys.public_from_seed(self.seed)
        self.assertTrue(verify_signature(r, pinned_pubkey=pub))
        self.assertFalse(verify_signature(r, pinned_pubkey=keys.public_from_seed(keys.generate_seed())))

    def test_records_policy_hash(self):
        r = self._receipt()
        self.assertEqual(r["policy_sha256"], self.policy.sha256())


class VerifyChecksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.seed = keys.generate_seed()

    def _bundle(self, scenario):
        out = Path(self.tmp, scenario)
        path, _ = build_bundle(scenario, str(out), seed=self.seed, policy_path=POLICY)
        return str(path), str(out)

    def test_clean_passes_all_four(self):
        path, ev = self._bundle("clean")
        res = verify_receipt(path, evidence_dir=ev, policy_path=POLICY)
        self.assertTrue(res.ok)
        self.assertIn("valid", res.summary())

    def test_a3_fails_at_step_four(self):
        path, ev = self._bundle("a3")
        res = verify_receipt(path, evidence_dir=ev, policy_path=POLICY)
        self.assertFalse(res.ok)
        self.assertEqual(res.first_failure.n, 4)
        self.assertIn("step 4", res.summary())
        # signature itself is still valid - the receipt honestly records a mismatch
        self.assertTrue(res.checks[1].ok)

    def test_tampered_receipt_fails_signature(self):
        path, ev = self._bundle("clean")
        r = json.loads(Path(path).read_text())
        r["recipient"] = "300-XXX-0000"
        Path(path).write_text(json.dumps(r))
        res = verify_receipt(path, evidence_dir=ev, policy_path=POLICY)
        self.assertFalse(res.ok)
        self.assertEqual(res.first_failure.n, 2)

    def test_swapped_evidence_file_fails_step_three(self):
        path, ev = self._bundle("clean")
        # overwrite an approved crop file with different bytes
        Path(ev, "approved_recipient.png").write_bytes(b"tampered")
        res = verify_receipt(path, evidence_dir=ev, policy_path=POLICY)
        self.assertFalse(res.ok)
        self.assertEqual(res.first_failure.n, 3)

    def test_without_evidence_still_checks_recorded(self):
        path, _ = self._bundle("a3")
        res = verify_receipt(path, evidence_dir=None, policy_path=POLICY)
        # step 3 skipped, but step 4 still catches the recorded mismatch
        self.assertFalse(res.ok)
        self.assertEqual(res.first_failure.n, 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
