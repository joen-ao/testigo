"""Spec 07 M9: the one-call check any agent can use (app.runtime.guard), with
the fixture pixel channel (no models)."""

import unittest

from app.adapters.meta.channels import FixtureChannel
from app.runtime.guard import check_screen, policy_summary
from tests.fixtures import captures as fx

PNG = b"\x89PNG\r\n\x1a\nnot-a-real-image"


class Screen(FixtureChannel):
    """Like the real channel, it also fills what the pixels show (`painted`)."""

    def __init__(self, painted):
        super().__init__()
        self.painted = painted

    def read_regions(self, capture):
        capture.rendered_lines = list(self.painted)
        return super().read_regions(capture)


def channel(address=fx.BUYER, amount=fx.TOTAL):
    painted = [x if x != fx.BUYER else address for x in fx._BASE_LINES]
    ch = Screen(painted)
    ch.set_regions(1, fx._regions(address=address, amount=amount))
    return ch


class GuardTests(unittest.TestCase):
    def test_an_honest_screen_asks_the_person(self):
        v = check_screen(PNG, "\n".join(fx._BASE_LINES), channel=channel())
        self.assertEqual(v["status"], "ok")
        self.assertTrue(v["needs_approval"])
        self.assertFalse(v["click_allowed"])
        self.assertEqual(v["approve"]["amount_cents"], 124000)
        self.assertIn("120 Harbor Road", v["approve"]["address"])

    def test_the_attackers_street_breaks_the_rules(self):
        a3 = [x if x != fx.BUYER else fx.A3 for x in fx._BASE_LINES]   # the live DOM shows it too
        v = check_screen(PNG, "\n".join(a3), channel=channel(address=fx.A3))
        self.assertEqual(v["status"], "policy_violation")
        self.assertNotIn("approve", v)
        self.assertFalse(v["click_allowed"])

    def test_hidden_instruction_in_the_page_code(self):
        text = "\n".join(list(fx._BASE_LINES) + [fx.INJECT])
        v = check_screen(PNG, text, channel=channel())
        self.assertEqual(v["status"], "divergence")
        self.assertIn(fx.INJECT, v["code_only_text"])

    def test_unreadable_screen_is_not_ok(self):
        v = check_screen(PNG, "", channel=FixtureChannel())
        self.assertEqual(v["status"], "cannot_verify")

    def test_needs_a_screenshot(self):
        with self.assertRaises(ValueError):
            check_screen(b"", "x", channel=channel())

    def test_policy_summary_has_no_key_material(self):
        p = policy_summary()
        self.assertEqual(p["ship_only_to"][0]["name"], "Larkspur Market")
        self.assertNotIn("signature", p)


if __name__ == "__main__":
    unittest.main()
