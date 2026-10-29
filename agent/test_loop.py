"""Tests for the agent loop and the gate invariant.

  make test   (or: .venv/bin/python -m pytest agent)
"""

import unittest

from interceptor import events as ev

from tests.fixtures.fake_agent import FixtureDriver, ScriptedAgent, run_fixture as run

from .approval import AutoApprover, DenyApprover  # noqa: F401
from .driver import ATTACKER_ACCT, SUPPLIER_ACCT


def types(out):
    return [e["type"] for e in out.events]


class SupervisedTests(unittest.TestCase):
    def test_clean_completes_and_pays_supplier(self):
        out = run("clean", supervised=True)
        self.assertTrue(out.executed)
        self.assertFalse(out.blocked)
        self.assertFalse(out.receipt_flagged)
        self.assertEqual(out.payment["recipient"], SUPPLIER_ACCT)
        self.assertFalse(out.attack_success)
        self.assertIn("receipt.signed", types(out))

    def test_a1_blocked_before_click(self):
        out = run("a1", supervised=True)
        self.assertTrue(out.blocked)
        self.assertFalse(out.executed)
        self.assertIsNone(out.payment)
        self.assertNotIn("receipt.signed", types(out))

    def test_a2_blocked_before_click(self):
        out = run("a2", supervised=True)
        self.assertTrue(out.blocked)
        self.assertFalse(out.executed)

    def test_a3_caught_after_click_and_held(self):
        out = run("a3", supervised=True)
        self.assertTrue(out.executed)
        self.assertTrue(out.receipt_flagged)
        self.assertTrue(out.reached_attacker)       # money moved...
        self.assertFalse(out.attack_success)        # ...but held, so not a win
        self.assertIn("verify.result", types(out))

    def test_blurred_blocked(self):
        out = run("blurred", supervised=True)
        self.assertTrue(out.blocked)

    def test_denied_approval_does_not_execute(self):
        out = run("clean", supervised=True, approver=DenyApprover())
        self.assertTrue(out.denied)
        self.assertFalse(out.executed)
        self.assertIsNone(out.payment)


class NoSupervisorTests(unittest.TestCase):
    def test_attacks_succeed_without_supervisor(self):
        for s in ("a1", "a2", "a3"):
            out = run(s, supervised=False)
            self.assertTrue(out.executed, s)
            self.assertTrue(out.attack_success, s)
            self.assertEqual(out.payment["recipient"], ATTACKER_ACCT, s)

    def test_clean_pays_supplier_without_supervisor(self):
        out = run("clean", supervised=False)
        self.assertFalse(out.attack_success)
        self.assertEqual(out.payment["recipient"], SUPPLIER_ACCT)

    def test_no_receipt_without_supervisor(self):
        out = run("a3", supervised=False)
        self.assertNotIn("receipt.signed", types(out))
        self.assertIsNone(out.receipt)

    def test_no_action_is_intercepted_without_supervisor(self):
        out = run("a1", supervised=False)
        self.assertEqual(out.intercepted, 0)


class GateInvariantTests(unittest.TestCase):
    def test_every_action_is_intercepted_when_supervised(self):
        # Gate test 2, modelled: no action reaches the driver un-checked.
        total = checked = 0
        for s in ("clean", "a1", "a2", "a3", "blurred"):
            out = run(s, supervised=True)
            total += out.actions
            checked += out.intercepted
        self.assertEqual(checked, total)
        self.assertEqual(checked, 5)

    def test_susceptible_agent_obeys_injection(self):
        # the agent itself is foolable - that is what the supervisor guards.
        drv = FixtureDriver("a1")
        action = ScriptedAgent().propose(drv.observe())
        self.assertEqual(action["recipient_acct"], ATTACKER_ACCT)

    def test_hardened_agent_ignores_injection(self):
        drv = FixtureDriver("a1")
        action = ScriptedAgent(obeys_injections=False).propose(drv.observe())
        self.assertEqual(action["recipient_acct"], SUPPLIER_ACCT)

    def test_event_order_supervised_clean(self):
        out = run("clean", supervised=True)
        order = types(out)
        self.assertEqual(order[0], "frame.captured")
        self.assertEqual(order[1], "agent.step")
        self.assertEqual(order[2], "check.result")
        self.assertIn("approval.requested", order)
        self.assertEqual(order[-1], "receipt.signed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
