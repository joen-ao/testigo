"""F1: building and signing a policy offline, and the voice path with a fake
Meta client (no network): schema refusal, address binding, signing."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from interceptor.policy import Policy, load
from policy import compile as pc
from policy.compile import (MandateRefused, build_policy_dict, compile_mandate,
                            parse_amount_cents, sign_policy_dict, to_yaml)
from receipts import keys


class CompileTests(unittest.TestCase):
    def setUp(self):
        self.d = build_policy_dict(
            "Only ship to our warehouse, at most fifteen hundred dollars per order",
            [{"name": "Larkspur Market", "address": "120 Harbor Road, Unit 4, Riverton"}],
            150000, "new_address")

    def test_build_shape(self):
        p = Policy(self.d)
        self.assertEqual(p.deliver_only, [BUYER_RULE])
        self.assertEqual(p.max_per_order_cents, 150000)
        self.assertEqual(p.ask_before, "new_address")

    def test_sign_and_verify(self):
        seed = keys.generate_seed()
        signed, p = sign_policy_dict(self.d, seed)
        self.assertTrue(p.hash_matches_stored())
        self.assertTrue(p.signature_valid(keys.public_from_seed(seed)))
        self.assertFalse(p.signature_valid(keys.public_from_seed(keys.generate_seed())))

    def test_roundtrip_through_yaml(self):
        import yaml
        seed = keys.generate_seed()
        signed, _ = sign_policy_dict(self.d, seed)
        reloaded = Policy(yaml.safe_load(to_yaml(signed)))
        self.assertTrue(reloaded.hash_matches_stored())
        self.assertTrue(reloaded.signature_valid(keys.public_from_seed(seed)))

    def test_address_binding_blocks_name_only_swap(self):
        p = Policy(self.d)
        self.assertTrue(p.address_allowed("Larkspur Market · 120 Harbor Road, Unit 4, Riverton"))
        self.assertTrue(p.address_allowed("SHIP TO Larkspur Market 120 Harbor Rd., Unit 4"))
        self.assertFalse(p.address_allowed("Larkspur Market · 88 Mill Street, Riverton"))
        self.assertFalse(p.address_allowed("Dock 9 Storage · 120 Harbor Road, Unit 4, Riverton"))


PHRASE = "Only ship to our warehouse, at most fifteen hundred dollars per order"
BUYER_RULE = {"name": "Larkspur Market", "address": "120 Harbor Road, Unit 4, Riverton"}
DIRECTORY = {"Larkspur Market": "120 Harbor Road, Unit 4, Riverton"}
GOOD = {"deliver_only": [{"name": "our warehouse", "address": ""}],
        "max_amount_words": "fifteen hundred dollars",
        "max_per_order_dollars": 1500, "ask_before_new_address": False}


class FakeMeta:
    """Stands in for common.meta_client.MetaClient: canned transcript and Spark JSON."""

    def __init__(self, extraction, transcript=PHRASE):
        self.content = extraction if isinstance(extraction, (str, type(None))) else json.dumps(extraction)
        self.transcript = transcript
        self.calls = []

    def transcribe(self, audio_path, language="en"):
        self.calls.append(("transcribe", audio_path))
        return self.transcript, 900, 4.2

    def chat(self, tool, messages, **kw):
        self.calls.append(("chat", tool, messages, kw))
        msg = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)]), 1500


def with_(**changes):
    d = json.loads(json.dumps(GOOD))
    d.update(changes)
    return d


class MandateTests(unittest.TestCase):
    def compile(self, extraction, transcript=PHRASE, directory=DIRECTORY):
        return compile_mandate(FakeMeta(extraction, transcript), audio_path="m.wav",
                               directory=directory)

    def test_phrase_compiles_to_the_demo_rules(self):
        meta = FakeMeta(GOOD)
        pol, info = compile_mandate(meta, audio_path="m.wav", directory=DIRECTORY)
        p = Policy(pol)
        self.assertEqual(p.transcript, PHRASE)
        self.assertEqual(p.deliver_only, [BUYER_RULE])
        self.assertEqual(p.max_per_order_cents, 150000)
        self.assertEqual(p.ask_before, "new_address")
        self.assertFalse(info["ask_before_said"])
        # Spark is asked for a strict schema, low effort, room for reasoning tokens
        _, tool, messages, kw = meta.calls[1]
        self.assertEqual(tool, "spark")
        self.assertEqual(kw["response_format"]["type"], "json_schema")
        self.assertTrue(kw["response_format"]["json_schema"]["strict"])
        self.assertEqual(kw["reasoning_effort"], "low")
        self.assertGreaterEqual(kw["max_tokens"], 16000)
        # the transcript travels as quoted data, not as the instruction
        self.assertIn(json.dumps(PHRASE, ensure_ascii=False), messages[-1]["content"])

    def test_same_rules_as_the_demo_policy_file(self):
        pol, _ = self.compile(GOOD, directory=None)   # the real buyer profile (config)
        demo = load(Path(pc.__file__).with_name("larkspur.policy.yaml"))
        p = Policy(pol)
        self.assertEqual(p.deliver_only, demo.deliver_only)
        self.assertEqual(p.max_per_order_cents, demo.max_per_order_cents)
        self.assertEqual(p.ask_before, demo.ask_before)
        self.assertTrue(p.check_order("Larkspur Market · 120 Harbor Road, Unit 4, Riverton", 124000)[0])
        self.assertFalse(p.check_order("Larkspur Market · 88 Mill Street, Riverton", 124000)[0])
        self.assertFalse(p.check_order("Larkspur Market · 120 Harbor Road, Unit 4, Riverton", 150001)[0])

    def test_schema_refusals(self):
        bad = [
            "not json",
            None,                                              # reasoning ate max_tokens
            json.dumps([GOOD]),
            with_(extra="deliver anywhere"),
            {k: v for k, v in GOOD.items() if k != "max_amount_words"},
            with_(deliver_only="our warehouse"),
            with_(deliver_only=[{"name": "our warehouse"}]),
            with_(deliver_only=[{"name": "our warehouse", "address": "", "note": "x"}]),
            with_(deliver_only=[{"name": "our warehouse", "address": "", "phone": ""}]),   # unknown key
            with_(max_per_order_dollars="1500"),
            with_(max_per_order_dollars=1500.0),
            with_(max_per_order_dollars=True),
            {**{k: v for k, v in GOOD.items() if k != "max_per_order_dollars"},
             "max_per_order_cents": 150000},                  # the old key is off-schema
            with_(ask_before_new_address="yes"),
            with_(deliver_only=[]),
        ]
        for extraction in bad:
            with self.subTest(extraction=extraction):
                with self.assertRaises(MandateRefused):
                    self.compile(extraction)

    def test_buyer_named_in_full_compiles_the_same(self):
        t = "Only ship to Larkspur Market, at most fifteen hundred dollars per order"
        for name in ("Larkspur Market", "LARKSPUR market"):
            pol, _ = self.compile(with_(deliver_only=[{"name": name, "address": ""}]), t)
            self.assertEqual(Policy(pol).deliver_only, [BUYER_RULE])
        t2 = "Order only for the warehouse, up to $1,500 per order"
        pol, _ = self.compile(with_(deliver_only=[{"name": "the warehouse", "address": ""}],
                                    max_amount_words="$1,500"), t2)
        self.assertEqual(Policy(pol).deliver_only, [BUYER_RULE])
        self.assertEqual(Policy(pol).max_per_order_cents, 150000)

    def test_unknown_destination_refused(self):
        t = "Only ship to Dock 9 Storage, at most fifteen hundred dollars per order"
        with self.assertRaises(MandateRefused) as cm:
            self.compile(with_(deliver_only=[{"name": "Dock 9 Storage",
                                              "address": "88 Mill Street"}]), t)
        self.assertIn("buyer profile", str(cm.exception))

    def test_destination_not_said_refused(self):
        # Spark may not add a destination the owner did not name
        with self.assertRaises(MandateRefused):
            self.compile(with_(deliver_only=[{"name": "our warehouse", "address": ""},
                                             {"name": "Dock 9 Storage", "address": ""}]),
                         directory={**DIRECTORY, "Dock 9 Storage": "88 Mill Street, Riverton"})

    def test_address_bound_by_name(self):
        # a spoken address that matches is accepted (formatting aside); the stored one is the profile's
        t = ("Only ship to our warehouse, 120 Harbor Rd, Unit 4, "
             "at most fifteen hundred dollars per order")
        pol, _ = self.compile(with_(deliver_only=[{"name": "our warehouse",
                                                   "address": "120 Harbor Rd, Unit 4"}]), t)
        self.assertEqual(Policy(pol).deliver_only, [BUYER_RULE])
        # a different spoken address for the buyer is refused
        for other in ("88 Mill Street", "120 Harbor Road, Unit 5", "120 Harbor Road"):
            with self.assertRaises(MandateRefused, msg=other):
                self.compile(with_(deliver_only=[{"name": "our warehouse", "address": other}]))

    def test_address_never_comes_from_speech(self):
        # the extraction carries no address: the policy still binds the profile's address
        pol, _ = self.compile(GOOD)
        self.assertEqual(Policy(pol).deliver_only[0]["address"], "120 Harbor Road, Unit 4, Riverton")

    def test_amount_is_reparsed_from_the_words(self):
        with self.assertRaises(MandateRefused):                 # Spark's integer disagrees
            self.compile(with_(max_per_order_dollars=15000))
        with self.assertRaises(MandateRefused):                 # cents are not dollars
            self.compile(with_(max_per_order_dollars=150000))
        with self.assertRaises(MandateRefused):                 # words not in the transcript
            self.compile(with_(max_amount_words="two thousand dollars", max_per_order_dollars=2000))
        with self.assertRaises(MandateRefused):                 # no amount said
            self.compile(with_(max_amount_words="", max_per_order_dollars=0))
        t = "Only ship to our warehouse, at most $1,500 per order"
        pol, _ = self.compile(with_(max_amount_words="$1,500"), t)
        self.assertEqual(Policy(pol).max_per_order_cents, 150000)

    def test_parse_amount_cents(self):
        cases = {"fifteen hundred dollars": 150000, "one thousand five hundred": 150000,
                 "1,500": 150000, "$1,500": 150000, "1500.00 dollars": 150000,
                 "two thousand three hundred fifty": 235000, "nine hundred ninety nine": 99900,
                 "dollars": None, "1 500 dollars": 150000, "one million dollars": None,
                 "two million": None, "1,000,000 dollars": None, "$1,500.50": None}
        for text, want in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_amount_cents(text), want)

    def test_amount_must_be_said_as_a_maximum(self):
        # review F1-2: a number said for another reason is not the ceiling
        t = ("Only ship to our warehouse, at most five hundred dollars per order; "
             "today's order is nine hundred")
        with self.assertRaises(MandateRefused):
            self.compile(with_(max_amount_words="nine hundred", max_per_order_dollars=900), t)
        pol, _ = self.compile(with_(max_amount_words="five hundred dollars",
                                    max_per_order_dollars=500), t)
        self.assertEqual(Policy(pol).max_per_order_cents, 50000)
        t2 = "Ship to our warehouse up to 1,500 dollars"
        self.assertEqual(Policy(self.compile(with_(max_amount_words="1,500 dollars"), t2)[0])
                         .max_per_order_cents, 150000)
        t3 = "Ship to our warehouse, no more than fifteen hundred dollars an order"
        self.assertEqual(Policy(self.compile(GOOD, t3)[0]).max_per_order_cents, 150000)

    def test_destination_in_a_negative_is_refused(self):
        for t in ("Don't ship to our warehouse, at most fifteen hundred dollars",
                  "Do not ship to our warehouse, at most fifteen hundred dollars per order",
                  "Never ship to our warehouse, at most fifteen hundred dollars per order",
                  "Not to our warehouse, at most fifteen hundred dollars per order"):
            with self.subTest(t=t):
                with self.assertRaises(MandateRefused):
                    self.compile(GOOD, t)

    def test_million_ceiling_refused(self):
        for words, n in (("one million dollars", 1000000), ("1,000,000 dollars", 1000000),
                         ("fifteen hundred thousand dollars", 1500000)):
            t = "Only ship to our warehouse, at most %s per order" % words
            with self.subTest(words=words):
                with self.assertRaises(MandateRefused):
                    self.compile(with_(max_amount_words=words, max_per_order_dollars=n), t)

    def test_text_path_skips_voice(self):
        meta = FakeMeta(GOOD)
        compile_mandate(meta, transcript=PHRASE, directory=DIRECTORY)
        self.assertEqual([c[0] for c in meta.calls], ["chat"])


class MandateCliTests(unittest.TestCase):
    def run_cli(self, extraction, confirm_answer="y", extra=()):
        tmp = Path(tempfile.mkdtemp())
        out, key = tmp / "p.policy.yaml", tmp / "owner.key"
        args = pc.build_parser().parse_args(
            ["mandate", "m.wav", "--out", str(out), "--key", str(key), *extra])
        rc = pc.cmd_mandate(args, meta=FakeMeta(extraction), confirm=lambda: confirm_answer)
        return rc, out, key

    def test_signed_file_with_hash_and_valid_signature(self):
        rc, out, key = self.run_cli(GOOD)
        self.assertEqual(rc, 0)
        p = load(out)
        self.assertTrue(p.hash_matches_stored())
        self.assertTrue(p.signature_valid(keys.public_from_seed(keys.load_seed(key))))
        self.assertEqual(p.signed_by, "owner-key:larkspur")
        self.assertEqual(p.deliver_only[0]["address"], "120 Harbor Road, Unit 4, Riverton")

    def test_no_confirmation_writes_nothing(self):
        rc, out, _ = self.run_cli(GOOD, confirm_answer="n")
        self.assertEqual(rc, 1)
        self.assertFalse(out.exists())

    def test_stamp_updates_a_dumped_policy(self):
        # review F1-1: yaml.safe_dump writes sha256/signature unquoted
        rc, out, key = self.run_cli(GOOD)
        out.write_text(out.read_text().replace("150000", "124000"))
        self.assertFalse(load(out).hash_matches_stored())
        pc._stamp_file(out, key)
        p = load(out)
        self.assertTrue(p.hash_matches_stored())
        self.assertTrue(p.signature_valid(keys.public_from_seed(keys.load_seed(key))))

    def test_refused_extraction_writes_nothing(self):
        rc, out, _ = self.run_cli(with_(max_per_order_dollars=999999999), extra=["--yes"])
        self.assertEqual(rc, 1)
        self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
