"""Tests for receipts: Ed25519, signing, and the four verify checks.

  make test   (or: .venv/bin/python -m pytest receipts)
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from common.config import POLICY_PATH
from interceptor.policy import load as load_policy
from tests.fixtures.bundles import build_bundle

from . import keys
from . import cli
from .bundle import crops_of, sign_order, write as write_bundle
from .receipt import BLOCKED, build, canonical, compare, norm_read, sha_crop, sign, verify_signature
from .verify import MalformedReceipt, verify_receipt

POLICY = str(POLICY_PATH)
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


_SYNTHETIC = []


def synthetic_examples():
    """A folder shaped like examples/ (clean/, a3/, pubkey.txt), built from the
    test fixtures with a throwaway key, for the CLI tests."""
    if not _SYNTHETIC:
        root = Path(tempfile.mkdtemp())
        seed = keys.generate_seed()
        for scenario in ("clean", "a3"):
            build_bundle(scenario, str(root / scenario), seed=seed, policy_path=POLICY)
        (root / "pubkey.txt").write_text(keys.public_from_seed(seed).hex() + "\n")
        _SYNTHETIC.append(root)
    return _SYNTHETIC[0]


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
        approved = {"amount": b"A", "address": b"R"}
        executed = executed or {"amount": b"A", "address": b"R"}
        return build(self.policy, "confirm order USD 1,240.00 -> ship to Larkspur Market",
                     124000, "Larkspur Market · 120 Harbor Road, Unit 4, Riverton",
                     approved, executed,
                     {"method": "passkey", "voice_transcript": "..."}, self.seed)

    def test_signature_valid_and_covers_body(self):
        r = self._receipt()
        self.assertTrue(verify_signature(r))
        r2 = dict(r)
        r2["amount_cents"] = 999999        # change a signed field
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
        r["address"] = "Dock 9 Storage · 88 Mill Street, Riverton"
        Path(path).write_text(json.dumps(r))
        res = verify_receipt(path, evidence_dir=ev, policy_path=POLICY)
        self.assertFalse(res.ok)
        self.assertEqual(res.first_failure.n, 2)

    def test_swapped_evidence_file_fails_step_three(self):
        path, ev = self._bundle("clean")
        # overwrite an approved crop file with different bytes
        Path(ev, "approved_address.png").write_bytes(b"tampered")
        res = verify_receipt(path, evidence_dir=ev, policy_path=POLICY)
        self.assertFalse(res.ok)
        self.assertEqual(res.first_failure.n, 3)

    def test_without_evidence_still_checks_recorded(self):
        path, _ = self._bundle("a3")
        res = verify_receipt(path, evidence_dir=None, policy_path=POLICY)
        # step 3 skipped, but step 4 still catches the recorded mismatch
        self.assertFalse(res.ok)
        self.assertEqual(res.first_failure.n, 4)


class ReadValueTests(unittest.TestCase):
    """Real captures: equal regions do not hash equal (SAM's boxes move), so
    step 4 decides on the values read from the crops; hashes guard the files."""

    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy(POLICY)
        cls.seed = keys.generate_seed()

    def _write(self, **kw):
        approved = {"amount": b"A1", "address": b"R1"}
        executed = kw.pop("executed", {"amount": b"A2", "address": b"R2"})   # moved boxes
        r = build(self.policy, "confirm order", 124000, "Larkspur Market · 120 Harbor Road, Unit 4, Riverton",
                  approved, executed, {"method": "console", "voice_transcript": ""}, self.seed,
                  approved_read={"amount": "USD 1,240.00", "address": "Larkspur Market · 120 Harbor Road, Unit 4, Riverton"},
                  **kw)
        d = Path(tempfile.mkdtemp())
        write_bundle(r, approved, executed, d)
        return r, d

    def test_same_read_values_pass_though_hashes_differ(self):
        r, d = self._write(executed_read={"amount": "USD 1,240.00",
                                          "address": "larkspur market l20 harbor rd unit 4"})
        self.assertEqual(r["comparison"], {"status": "match", "by": "read"})
        res = verify_receipt(str(d / "receipt.json"), evidence_dir=str(d), policy_path=POLICY)
        self.assertTrue(res.ok, res.summary())

    def test_changed_address_read_fails_step_four(self):
        r, d = self._write(executed_read={"amount": "USD 1,240.00",
                                          "address": "Dock 9 Storage · 88 Mill Street"})
        self.assertEqual(r["comparison"]["status"], "mismatch")
        res = verify_receipt(str(d / "receipt.json"), evidence_dir=str(d), policy_path=POLICY)
        self.assertEqual(res.first_failure.n, 4)
        self.assertTrue(res.checks[1].ok)
        self.assertEqual(res.summary(), "Evidence mismatch at step 4")

    def test_swapped_executed_file_fails_step_four(self):
        _, d = self._write(executed_read={"amount": "1240.00",
                                          "address": "Larkspur Market · 120 Harbor Road, Unit 4, Riverton"})
        Path(d, "executed_amount.png").write_bytes(b"tampered")
        res = verify_receipt(str(d / "receipt.json"), evidence_dir=str(d), policy_path=POLICY)
        self.assertEqual(res.first_failure.n, 4)
        self.assertIn("file", res.first_failure.detail)

    def test_nothing_captured_after_click_is_reported_not_invented(self):
        r, d = self._write(executed=None)
        self.assertIsNone(r["executed"])
        self.assertEqual(r["comparison"]["status"], "pending")
        res = verify_receipt(str(d / "receipt.json"), evidence_dir=str(d), policy_path=POLICY)
        self.assertEqual(res.first_failure.n, 4)
        self.assertIn("not recorded", res.summary())

    def test_blocked_receipt_has_no_executed_and_no_step_four(self):
        r, d = self._write(status=BLOCKED, blocked_at="review", executed=None)
        self.assertIsNone(r["executed"])
        self.assertEqual(r["blocked_at"], "review")
        res = verify_receipt(str(d / "receipt.json"), evidence_dir=str(d), policy_path=POLICY)
        self.assertTrue(res.ok, res.summary())
        self.assertIn("not applicable", res.checks[3].detail)

    def test_id_and_time_are_generated(self):
        a, _ = self._write(executed_read=None)
        b, _ = self._write(executed_read=None)
        self.assertNotEqual(a["id"], b["id"])
        self.assertTrue(a["time"].endswith("-05:00"))


class ExamplesTests(unittest.TestCase):
    """The published examples (scripts/make_examples.py) keep verifying."""

    def test_examples(self):
        self._check(EXAMPLES)

    def test_examples_verify_from_a_fresh_clone(self):
        # No --policy, no runs/: step 1 finds the committed policy by hash.
        pub = (EXAMPLES / "pubkey.txt").read_text().strip()
        code, out, _ = _run_cli("verify", str(EXAMPLES / "clean/receipt.json"), "--pubkey", pub)
        self.assertEqual(code, 0, out)
        self.assertIn("policy/larkspur.policy.yaml", out)
        code, out, _ = _run_cli("verify", str(EXAMPLES / "a3/receipt.json"), "--pubkey", pub)
        self.assertEqual(code, 1, out)
        self.assertIn("[1/4] \u2713", out)
        self.assertIn("[3/4] \u2713", out)
        self.assertIn("[4/4] \u2717 executed", out)
        self.assertIn("88 Mill Street", out)
        self.assertIn("Evidence mismatch at step 4", out)

    def test_examples_name_the_delivery_crops(self):
        from .receipt import CROP_NAMES
        for n in ("clean", "a3"):
            names = sorted(p.name for p in (EXAMPLES / n).glob("*.png"))
            self.assertEqual(names, sorted("%s_%s.png" % (s, c) for s in ("approved", "executed")
                                           for c in CROP_NAMES))

    def test_synthetic_examples_like_the_published_ones(self):
        self._check(synthetic_examples())

    def _check(self, root):
        pub = bytes.fromhex((root / "pubkey.txt").read_text().strip())
        clean = verify_receipt(str(root / "clean/receipt.json"), evidence_dir=str(root / "clean"),
                               policy_path=POLICY, pinned_pubkey=pub)
        self.assertTrue(clean.ok)
        self.assertEqual(clean.summary(), "Signature valid — evidence hashes match")
        a3 = verify_receipt(str(root / "a3/receipt.json"), evidence_dir=str(root / "a3"),
                            policy_path=POLICY, pinned_pubkey=pub)
        self.assertEqual(a3.summary(), "Evidence mismatch at step 4")


def _run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


class HardeningTests(unittest.TestCase):
    """Code-review fixes: missing evidence never matches, malformed receipts
    fail cleanly, partial captures are recorded honestly."""

    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy(POLICY)
        cls.seed = keys.generate_seed()

    def _signed(self, body, files=None):
        d = Path(tempfile.mkdtemp())
        base = {"id": "rcpt_t", "policy_sha256": self.policy.sha256(), "status": "confirmed"}
        base.update(body)
        r = sign(base, self.seed)
        (d / "receipt.json").write_text(json.dumps(r))
        for name, data in (files or {}).items():
            (d / name).write_bytes(data)
        return d

    def _raw(self, obj):
        d = Path(tempfile.mkdtemp())
        (d / "receipt.json").write_text(json.dumps(obj))
        return str(d / "receipt.json")

    # 1. a missing hash or file never counts as a match
    def test_empty_approved_and_junk_executed_fail(self):
        d = self._signed({"approved": {}, "executed": {"foo": "bar"}})
        res = verify_receipt(str(d / "receipt.json"), policy_path=POLICY)
        self.assertFalse(res.ok)
        self.assertFalse(res.checks[2].ok)
        self.assertFalse(res.checks[3].ok)
        code, out, _ = _run_cli("verify", str(d / "receipt.json"), "--policy", POLICY)
        self.assertEqual(code, 1)

    def test_non_hex_hash_fails(self):
        h = sha_crop(b"A")
        d = self._signed({"approved": {"amount": h, "address": "XYZ"},
                          "executed": {"amount": h, "address": "XYZ"}})
        res = verify_receipt(str(d / "receipt.json"), policy_path=POLICY)
        self.assertEqual(res.first_failure.n, 3)
        self.assertIn("sha256", res.checks[2].detail)

    def test_missing_evidence_files_fail(self):
        ha, hr = sha_crop(b"A"), sha_crop(b"R")
        body = {"approved": {"amount": ha, "address": hr},
                "executed": {"amount": ha, "address": hr}}
        d = self._signed(body, {"approved_amount.png": b"A", "approved_address.png": b"R",
                                "executed_amount.png": b"A"})
        res = verify_receipt(str(d / "receipt.json"), evidence_dir=str(d), policy_path=POLICY)
        self.assertTrue(res.checks[2].ok)
        self.assertEqual(res.first_failure.n, 4)
        self.assertIn("executed address file missing", res.checks[3].detail)
        (d / "approved_address.png").unlink()
        res = verify_receipt(str(d / "receipt.json"), evidence_dir=str(d), policy_path=POLICY)
        self.assertEqual(res.first_failure.n, 3)
        self.assertIn("missing", res.checks[2].detail)

    def test_extra_executed_crop_name_fails(self):
        ha, hr = sha_crop(b"A"), sha_crop(b"R")
        d = self._signed({"approved": {"amount": ha, "address": hr},
                          "executed": {"amount": ha, "address": hr, "memo": ha}})
        res = verify_receipt(str(d / "receipt.json"), policy_path=POLICY)
        self.assertEqual(res.first_failure.n, 4)
        self.assertIn("memo", res.checks[3].detail)

    # 2. malformed receipts: a clear message, exit 1, no traceback
    def test_malformed_receipts_exit_1(self):
        h = sha_crop(b"A")
        good = {"approved": {"amount": h, "address": h}, "executed": None}
        cases = [
            [1, 2, 3],
            dict(good, read={"approved": "124000", "executed": None}),
            dict(good, executed="abc"),
            dict(good, pubkey=12345, signature="ed25519:00"),
            dict(good, approved="abc"),
            dict(good, signature=7),
        ]
        for obj in cases:
            path = self._raw(obj)
            with self.assertRaises(MalformedReceipt):
                verify_receipt(path, policy_path=POLICY)
            code, out, _ = _run_cli("verify", path, "--policy", POLICY)
            self.assertEqual(code, 1, obj)
            self.assertTrue(out.startswith("Malformed receipt: "), out)

    def test_not_json_is_malformed(self):
        d = Path(tempfile.mkdtemp())
        (d / "receipt.json").write_text("{nope")
        code, out, _ = _run_cli("verify", str(d / "receipt.json"), "--policy", POLICY)
        self.assertEqual(code, 1)
        self.assertIn("Malformed receipt: not valid JSON", out)

    def test_bad_pubkey_is_usage_error(self):
        clean = str(synthetic_examples() / "clean/receipt.json")
        for bad in ("zz", "abcd"):
            code, out, err = _run_cli("verify", clean, "--pubkey", bad)
            self.assertEqual(code, 2)
            self.assertIn("--pubkey must be 64 hex", err)

    # 3. a partial executed capture records only what was written
    def _event(self):
        return {"amount_cents": 124000, "address": "Larkspur Market · 120 Harbor Road, Unit 4, Riverton"}

    def test_crops_of_returns_partial_or_none(self):
        self.assertEqual(crops_of(SimpleNamespace(crops={"amount": b"A"})), {"amount": b"A"})
        self.assertIsNone(crops_of(SimpleNamespace(crops={})))
        self.assertIsNone(crops_of(None))

    def test_partial_executed_capture_recorded_honestly(self):
        d = Path(tempfile.mkdtemp())
        vr = {"executed": {"amount": "f" * 64, "address": "e" * 64}}
        r, path = sign_order(self.policy, self._event(), {"method": "console"},
                               {"amount": b"A", "address": b"R"}, self.seed,
                               executed_crops={"amount": b"A2"}, verify_result=vr, run_dir=d)
        self.assertEqual(r["executed"], {"amount": sha_crop(b"A2")})
        self.assertTrue((d / "executed_amount.png").is_file())
        self.assertFalse((d / "executed_address.png").exists())
        res = verify_receipt(str(path), evidence_dir=str(d), policy_path=POLICY)
        self.assertEqual(res.first_failure.n, 4)
        self.assertIn("address hash not recorded", res.checks[3].detail)

    def test_no_executed_crops_means_not_captured(self):
        d = Path(tempfile.mkdtemp())
        vr = {"executed": {"amount": "f" * 64, "address": "e" * 64}}
        r, path = sign_order(self.policy, self._event(), {"method": "console"},
                               {"amount": b"A", "address": b"R"}, self.seed,
                               executed_crops=None, verify_result=vr, run_dir=d)
        self.assertIsNone(r["executed"])
        res = verify_receipt(str(path), evidence_dir=str(d), policy_path=POLICY)
        self.assertIn("not recorded", res.summary())

    def test_full_executed_capture_with_reads_passes(self):
        d = Path(tempfile.mkdtemp())
        r, path = sign_order(self.policy, self._event(), {"method": "console"},
                               {"amount": b"A", "address": b"R"}, self.seed,
                               executed_crops={"amount": b"A2", "address": b"R2"},
                               executed_read={"amount": "$1,240",
                                              "address": "Ship to 120 Harbor Road, Unit 4"},
                               run_dir=d)
        self.assertEqual(r["comparison"], {"status": "match", "by": "read"})
        res = verify_receipt(str(path), evidence_dir=str(d), policy_path=POLICY)
        self.assertTrue(res.ok, res.summary())

    # 4. approved read without executed read is pending, not by hash
    def test_compare_pending_when_executed_read_missing(self):
        h = {"amount": "a" * 64, "address": "b" * 64}
        self.assertEqual(compare({"amount": "1"}, None, h, dict(h)),
                         {"status": "pending", "by": None})
        self.assertEqual(compare(None, {"amount": "1"}, h, dict(h)),
                         {"status": "pending", "by": None})
        self.assertEqual(compare(None, None, h, dict(h)), {"status": "match", "by": "hash"})

    def test_receipt_without_executed_read_is_pending_at_step_4(self):
        d = Path(tempfile.mkdtemp())
        same = {"amount": b"A", "address": b"R"}
        r, path = sign_order(self.policy, self._event(), {"method": "console"},
                               same, self.seed, executed_crops=dict(same), run_dir=d)
        self.assertEqual(r["comparison"]["status"], "pending")
        res = verify_receipt(str(path), evidence_dir=str(d), policy_path=POLICY)
        self.assertEqual(res.first_failure.n, 4)
        self.assertEqual(res.summary(), "Executed evidence not compared at step 4")

    # 5. say whether the key was pinned
    def test_key_note_unpinned_and_pinned(self):
        root = synthetic_examples()
        code, out, _ = _run_cli("verify", str(root / "clean/receipt.json"))
        self.assertEqual(code, 0)
        self.assertIn("Key: embedded in the receipt (not pinned; pass --pubkey to pin it)", out)
        self.assertEqual(out.strip().splitlines()[-1], "Signature valid — evidence hashes match")
        pub = (root / "pubkey.txt").read_text().strip()
        code, out, _ = _run_cli("verify", str(root / "clean/receipt.json"), "--pubkey", pub)
        self.assertEqual(code, 0)
        self.assertNotIn("not pinned", out)
        code, out, _ = _run_cli("verify", str(root / "a3/receipt.json"), "--pubkey", pub)
        self.assertEqual(code, 1)
        self.assertEqual(out.strip().splitlines()[-1], "Evidence mismatch at step 4")


class NormReadTests(unittest.TestCase):
    """The address compares by its canonical street address: labels, names and
    the city differ per screen and do not count."""

    BUYER = "120 harbor road unit 4"

    def test_labels_names_and_city_do_not_count(self):
        a = norm_read("address", "SHIP TO Larkspur Market · 120 Harbor Road, Unit 4, Riverton")
        b = norm_read("address", "To: 120 Harbor Road Unit 4")
        self.assertEqual(a, self.BUYER)
        self.assertEqual(a, b)

    def test_other_address_differs(self):
        self.assertNotEqual(norm_read("address", "120 Harbor Road, Unit 4"),
                            norm_read("address", "88 Mill Street"))
        # the same number and name on another street type is another address
        self.assertNotEqual(norm_read("address", "120 Harbor Road"),
                            norm_read("address", "120 Harbor Street"))
        self.assertNotEqual(norm_read("address", "120 Harbor Road, Unit 4"),
                            norm_read("address", "121 Harbor Road, Unit 4"))
        self.assertNotEqual(norm_read("address", "120 Harbor Road, Unit 4"),
                            norm_read("address", "120 Harbor Road, Unit 5"))
        self.assertNotEqual(norm_read("address", "120 Harbor Road, Unit 4"),
                            norm_read("address", "120 Harbor Road"))

    def test_addresses_sorted_and_deduplicated(self):
        self.assertEqual(
            norm_read("address", "88 Mill St / 120 Harbor Road, Unit 4 120 Harbor Rd. Unit 4"),
            "120 harbor road unit 4,88 mill street")

    def test_without_address_letters_and_digits(self):
        self.assertEqual(norm_read("address", "Larkspur Market!"), "larkspurmarket")
        self.assertEqual(norm_read("address", "eighty-eight Mill Street"), "eightyeightmillstreet")
        self.assertEqual(norm_read("amount", "USD 1,240.00"), "124000")
        self.assertIsNone(norm_read("address", None))


class ReadNormalizationTests(unittest.TestCase):
    """Review of F8: what a reader may return for the same value compares equal."""

    def test_street_types_and_abbreviations(self):
        cases = {
            "120 harbor road": ("120 Harbor Road", "120 HARBOR ROAD", "120 Harbor Rd", "120 Harbor Rd.",
                                "120 harbor rd"),
            "88 mill street": ("88 Mill Street", "88 Mill St", "88 Mill St.", "88 MILL ST"),
            "5 oak avenue": ("5 Oak Avenue", "5 Oak Ave", "5 Oak Ave."),
            "7 sunset boulevard": ("7 Sunset Boulevard", "7 Sunset Blvd", "7 Sunset Blvd."),
            "9 cherry tree lane": ("9 Cherry Tree Lane", "9 Cherry Tree Ln"),
            "300 bay drive": ("300 Bay Drive", "300 Bay Dr", "300 Bay Dr."),
            "12 5th avenue": ("12 5th Avenue", "12 5TH AVE"),
        }
        for want, forms in cases.items():
            for f in forms:
                self.assertEqual(norm_read("address", f), want, f)

    def test_complements(self):
        cases = {"120 Harbor Road, Unit 4": "120 harbor road unit 4",
                 "120 Harbor Road Unit 4": "120 harbor road unit 4",
                 "120 Harbor Road, UNIT 04": "120 harbor road unit 4",
                 "120 Harbor Road, Suite B": "120 harbor road suite b",
                 "120 Harbor Road, Ste B": "120 harbor road suite b",
                 "120 Harbor Road, Apt 2": "120 harbor road apt 2",
                 "120 Harbor Road, Apartment 2": "120 harbor road apt 2",
                 "120 Harbor Road, Bldg C": "120 harbor road bldg c",
                 "120 Harbor Road, Dock 9": "120 harbor road dock 9",
                 "120 Harbor Road, Unit 4B": "120 harbor road unit 4b"}
        for s, want in cases.items():
            self.assertEqual(norm_read("address", s), want, s)
        for other in ("120 Harbor Road, Suite 4", "120 Harbor Road, Apt 4", "120 Harbor Road, Dock 4",
                      "120 Harbor Road, Unit 4A"):
            self.assertNotEqual(norm_read("address", other), "120 harbor road unit 4", other)

    def test_directionals(self):
        for s in ("120 N Harbor Road", "120 North Harbor Road", "120 N. Harbor Rd"):
            self.assertEqual(norm_read("address", s), "120 north harbor road", s)
        self.assertEqual(norm_read("address", "120 Harbor Road S"), "120 harbor road south")
        self.assertEqual(norm_read("address", "120 Harbor Road, West, Unit 4"),
                         "120 harbor road west unit 4")
        # before the name and after the type are different addresses
        self.assertNotEqual(norm_read("address", "120 North Harbor Road"),
                            norm_read("address", "120 Harbor Road North"))

    def test_spacing_and_punctuation(self):
        for s in ("120 Harbor Road, Unit 4", "120  Harbor  Road ,  Unit  4", "120 Harbor Road,Unit 4",
                  "120 Harbor Rd., Unit 4.", "120\tHarbor Road\nUnit 4"):
            self.assertEqual(norm_read("address", s), "120 harbor road unit 4", s)

    def test_ocr_digit_slips(self):
        # I, l and O misread for 1, 1 and 0 in the house number
        for s in ("I20 Harbor Road, Unit 4", "l20 Harbor Road, Unit 4", "12O Harbor Road, Unit 4",
                  "l2O Harbor Road, Unit 4"):
            self.assertEqual(norm_read("address", s), "120 harbor road unit 4", s)
        self.assertEqual(norm_read("address", "8O Mill Street"), "80 mill street")
        self.assertNotEqual(norm_read("address", "8O Mill Street"), "88 mill street")
        # a number with no real digit is not a number
        self.assertEqual(norm_read("address", "IO Harbor Road"), "ioharborroad")

    def test_leading_zeros_do_not_count(self):
        self.assertEqual(norm_read("address", "0120 Harbor Road, Unit 004"), "120 harbor road unit 4")

    def test_lookalike_letters_are_not_the_address(self):
        # a Cyrillic "о" in the name or the type: not read as the address at all
        for s in ("120 Harbоr Road, Unit 4", "120 Harbor Rоad, Unit 4"):
            self.assertNotEqual(norm_read("address", s), "120 harbor road unit 4", s)

    def test_same_value_from_each_screen(self):
        same = ["120 Harbor Road, Unit 4, Riverton", "Ship to: Larkspur Market · 120 Harbor Road, Unit 4, Riverton",
                "120 Harbor Road, Unit 4, Riverton Larkspur Market", "SHIPPED TO 120 Harbor Rd. Unit 4",
                "Ship to: 120 HARBOR RD UNIT 4 RIVERTON (simulated)", "l20 Harbor Rd, Unit 4"]
        for s in same:
            self.assertEqual(norm_read("address", s), "120 harbor road unit 4", s)
        self.assertNotEqual(norm_read("address", "Dock 9 Storage · 88 Mill Street, Riverton"),
                            "120 harbor road unit 4")

    def test_not_an_address(self):
        # an order number, a total or a street word without a number are not addresses
        self.assertEqual(norm_read("address", "Order PO-2041"), "orderpo2041")
        self.assertEqual(norm_read("address", "Harbor Road"), "harborroad")
        self.assertEqual(norm_read("address", "120 Harbor"), "120harbor")
        self.assertEqual(norm_read("address", "PO-2041 Harbor Road"), "po2041harborroad")
        self.assertEqual(norm_read("address", "USD 1,240.00 Harbor Road"), "usd124000harborroad")
        self.assertEqual(norm_read("address", "120 Harbor Roadway"), "120harborroadway")

    def test_trailing_directional_city_or_complement_is_another_address(self):
        # review of cebf0f4 (security, ported): the parse must not stop at the type
        buyer = norm_read("address", "120 Harbor Road, Unit 4, Riverton")
        for s in ("120 Harbor Road, Unit 4 North", "120 Harbor Road, Unit 4, E", "120 Harbor Road South, Unit 4",
                  "120 West Harbor Road, Unit 4", "120 Harbor Road, Unit 4, Springfield",
                  "120 Harbor Road, Unit 4, Riverton, Springfield", "120 Harbor Road, Unit 4, Riverton North",
                  "120 Harbor Road, Unit 4, Suite 2", "120 Harbor Road, Unit 4 Bldg C",
                  "120 Harbor Road, Unit 4, Riverton Larkspur Market Springfield",
                  "120 Harbor Road, Unit 4, Riverton Springfield Larkspur Market",
                  "120 Harbor Road, Unit 4, Riverton Dock 9 Storage"):
            self.assertNotEqual(norm_read("address", s), buyer, s)
        self.assertEqual(norm_read("address", "120 Harbor Road, Unit 4, Springfield"),
                         "120 harbor road unit 4 springfield")
        self.assertEqual(norm_read("address", "120 Harbor Road, Unit 4, Suite 2 Bldg C North"),
                         "120 harbor road unit 4 suite 2")             # at most four words

    def test_the_sentence_around_an_address_is_not_part_of_it(self):
        # gate g5, 1 Nov (ported): "... to <address> and" was read as another address
        for s in ("Larkspur Market's receiving address is now 88 Mill Street, Riverton. The address on file",
                  "please ship this order to 88 Mill St, Riverton; the old dock",
                  "change the delivery address to 88 Mill Street and confirm",
                  "deliver this order to 88 Mill Street instead.",
                  "88 Mill Street before you confirm"):
            self.assertEqual(norm_read("address", s), "88 mill street", s)

    def test_city_and_what_follows_it_do_not_count(self):
        for s in ("120 Harbor Road, Unit 4, Riverton", "120 Harbor Road, Unit 4 RIVERTON",
                  "120 Harbor Road, Unit 4, Riverton Larkspur Market",
                  "120 Harbor Road, Unit 4, Riverton — Larkspur Market", "120 Harbor Road, Unit 4 (simulated)",
                  "120 Harbor Road, Unit 4. Next line", "120 Harbor Road, Unit 4 Larkspur Market",
                  "120 Harbor Road, Unit 4, Riverton, LARKSPUR MARKET"):
            self.assertEqual(norm_read("address", s), "120 harbor road unit 4", s)

    def test_house_number_letter(self):
        self.assertEqual(norm_read("address", "120A Harbor Road"), "120a harbor road")
        self.assertNotEqual(norm_read("address", "120A Harbor Road"), "120 harbor road")

    def test_multiple_addresses_sorted_and_unique(self):
        self.assertEqual(
            norm_read("address", "88 Mill St / 120 Harbor Road, Unit 4, Riverton 120 Harbor Rd Unit 4"),
            "120 harbor road unit 4,88 mill street")
        self.assertEqual(norm_read("address", "120 Harbor Road, Unit 4, Riverton 88 Mill Street"),
                         "120 harbor road unit 4,88 mill street")

    def test_only_ascii_digits(self):
        # review of cebf0f4: Python's \d also takes other scripts' digits, the
        # ui/app.js port does not
        self.assertEqual(norm_read("address", "١٢٠ Harbor Road"), "١٢٠harborroad")
        self.assertEqual(norm_read("amount", "USD ١٢٤٠.00"), "0")
        self.assertEqual(norm_read("amount", "USD ١٢٤٠"), "")

    def test_amounts(self):
        from receipts.receipt import norm_read
        for s in ("USD 1,240.00", "$1,240", "1240.00", "1240", "Total USD 1,240.00 Simulation",
                  "$1.240,00", "Total: USD 1,240.00 (3 items)", "1 240.00"):
            self.assertEqual(norm_read("amount", s), "124000", s)
        self.assertEqual(norm_read("amount", "USD 1,240.50"), "124050")
        self.assertNotEqual(norm_read("amount", "USD 1,250.00"), "124000")


if __name__ == "__main__":
    unittest.main(verbosity=2)
