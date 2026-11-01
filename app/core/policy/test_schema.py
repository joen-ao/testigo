"""Spec 10 P2: a malformed policy is never enforced, and never signed."""

import copy
import tempfile
import unittest
from pathlib import Path

import yaml

from app.common.config import POLICY_PATH
from app.core.policy.model import load
from app.core.policy.schema import PolicyInvalid, validate_policy


def committed():
    return yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))


def with_rule(data, key, value):
    d = copy.deepcopy(data)
    d["rules"] = [r for r in d["rules"] if key not in r] + ([{key: value}] if value is not ... else [])
    return d


class SchemaTests(unittest.TestCase):
    def test_the_committed_policy_is_well_formed(self):
        self.assertEqual(validate_policy(committed()), [])

    def test_each_problem_is_named(self):
        base = committed()
        bad = {
            "unknown field": dict(base, admin=True),
            "version": dict(base, version=2),
            "max_per_order_cents": with_rule(base, "max_per_order_cents", -5),
            "whole number": with_rule(base, "max_per_order_cents", 12.5),
            "1 to": with_rule(base, "max_per_order_cents", True),
            "at least one place": with_rule(base, "deliver_only", []),
            "readable street address": with_rule(base, "deliver_only", [{"name": "Larkspur Market", "address": "somewhere"}]),
            "exactly name and address": with_rule(base, "deliver_only", [{"name": "X", "address": "1 A Road", "note": "y"}]),
            "ask_before": with_rule(base, "ask_before", "never"),
            "unknown rule": dict(base, rules=base["rules"] + [{"allow_all": True}]),
            "given twice": dict(base, rules=base["rules"] + [{"max_per_order_cents": 1}]),
            "non-empty list": dict(base, rules=[]),
            "not a mapping": ["rules"],
        }
        for want, data in bad.items():
            probs = validate_policy(data)
            self.assertTrue(probs, want)
            self.assertTrue(any(w in p for p in probs for w in want.split(" or ")), (want, probs))

    def test_load_refuses_a_malformed_policy_unless_only_looked_up(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.policy.yaml"
            p.write_text(yaml.safe_dump(with_rule(committed(), "max_per_order_cents", 0)))
            with self.assertRaises(PolicyInvalid):
                load(p)
            self.assertEqual(load(p, validate=False).max_per_order_cents, 0)

    def test_never_signed(self):
        from app.core.evidence import keys
        from app.core.policy.compile import sign_policy_dict
        with self.assertRaises(PolicyInvalid):
            sign_policy_dict(with_rule(committed(), "ask_before", "sometimes"), keys.generate_seed())


if __name__ == "__main__":
    unittest.main()
