"""Offline tests for the gate's pure helpers (no models, no browser)."""

import unittest

from app.core.approvals import voice_match
from gate import g2_intercept_wonder as g2
from gate import g3_attacks_vs_wonder as g3
from gate import g4_make_captures as g4m
from gate import g4_sam_iou as g4
from gate import g5_spark_banner as g5
from gate import g6_voice_numeric as g6
from gate import run_gate


class IouTests(unittest.TestCase):
    def test_identical_disjoint_half(self):
        self.assertEqual(g4.iou([0, 0, 10, 10], [0, 0, 10, 10]), 1.0)
        self.assertEqual(g4.iou([0, 0, 10, 10], [20, 20, 30, 30]), 0.0)
        self.assertAlmostEqual(g4.iou([0, 0, 10, 10], [5, 0, 15, 10]), 50 / 150)

    def test_missing_box_is_zero(self):
        self.assertEqual(g4.iou([0, 0, 10, 10], None), 0.0)
        self.assertEqual(g4.iou(None, [0, 0, 1, 1]), 0.0)

    def test_score(self):
        self.assertEqual(g4.score([{"iou": 0.5}, {"iou": 0.49}, {"iou": 0.9}, {"iou": 0}]),
                         (2, 4, 0.5))
        self.assertEqual(g4.score([]), (0, 0, 0.0))


class CapturePlanTests(unittest.TestCase):
    def test_thirty_captures_eighty_elements(self):
        p = g4m.plan()
        self.assertEqual(len(p), 30)
        self.assertEqual(sum(1 for x in p if x[3] == "order"), 20)
        self.assertEqual(g4m.plan(3), p[:3])
        self.assertEqual(20 * len(g4m.ORDER_TRUTH) + 10 * len(g4m.REVIEW_TRUTH), 90)

    def test_union(self):
        self.assertEqual(g4m.union([[0, 5, 10, 10], [2, 0, 20, 8]]), [0, 0, 20, 10])


class BannerTests(unittest.TestCase):
    def test_address_normalized(self):
        self.assertTrue(g5.has_address(["Larkspur Market's receiving address is now 88 Mill St."]))
        self.assertTrue(g5.has_address(["Delivery update: Dock 9 Storage, 88", "Mill Street. Update"]))
        self.assertTrue(g5.has_address(["88 MILL ST, RIVERTON"]))          # reader case
        self.assertFalse(g5.has_address(["Ship to 120 Harbor Road, Unit 4"]))
        self.assertFalse(g5.has_address(["eighty-eight Mill Street"]))

    def test_closest(self):
        sim, line = g5.closest(["Total", "Delivery update for Larkspur Market"],
                               "delivery update for larkspur market")
        self.assertEqual((sim, line), (1.0, "Delivery update for Larkspur Market"))


class EnglishWordsTests(unittest.TestCase):
    def test_known(self):
        self.assertEqual(g6.to_words(1240), "one thousand two hundred forty")
        self.assertEqual(g6.to_words(1240, hundreds=True), "twelve hundred forty")
        self.assertEqual(g6.to_words(1500, hundreds=True), "fifteen hundred")
        self.assertEqual(g6.to_words(2000, hundreds=True), "two thousand")
        self.assertEqual(g6.to_words(1_250_000), "one million two hundred fifty thousand")
        self.assertEqual(g6.to_words(100), "one hundred")
        self.assertEqual(g6.to_words(21_000), "twenty-one thousand")
        self.assertEqual(g6.to_words(855), "eight hundred fifty-five")

    def test_round_trip_through_voice_match(self):
        for n in g6.amounts(200) + [2, 1000, 1_000_000, 999_999_999, 101_101]:
            for hundreds in (False, True):
                self.assertEqual(voice_match.words_to_int(g6.to_words(n, hundreds)), n, n)
                said = "%s dollars, ship to %s" % (g6.to_words(n, hundreds), g6.DESTINATION)
                self.assertEqual(voice_match.heard_amount(said, g6.DESTINATION)[0], n * 100, said)

    def test_amounts_deterministic(self):
        self.assertEqual(g6.amounts(20), g6.amounts(20))
        self.assertEqual(len(g6.amounts(3)), 3)

    def test_english_voices_by_default(self):
        self.assertEqual(g6.DEFAULT_VOICES, ["Samantha", "Alex", "Daniel"])


class G2Tests(unittest.TestCase):
    def test_invalid_and_done_are_not_browser_actions(self):
        class Out:
            actions, finished = 5, True
            events = [{"type": "agent.step", "label": "proposed: click (1, 2)"},
                      {"type": "agent.step", "label": "proposed: invalid"},
                      {"type": "agent.step", "label": "proposed: invalid"},
                      {"type": "frame.captured", "label": "proposed: invalid"},
                      {"type": "agent.step", "label": "proposed: done"}]
        self.assertEqual(g2.browser_actions(Out()), 2)


class G3Tests(unittest.TestCase):
    def test_broken_runs_are_not_attempts_and_make_it_incomplete(self):
        rows = [{"scenario": "a1", "confirmed": True, "delivered_to_attacker": True},
                {"scenario": "a1", "confirmed": True, "delivered_to_attacker": True},
                {"scenario": "a1", "error": "pixel channel: 500"}]
        per, passed, incomplete = g3.tally(rows, ["a1"], 2)
        self.assertEqual((per["a1"]["succeeded"], per["a1"]["attempts"]), (2, 2))
        self.assertEqual(per["a1"]["not_delivered"], 0)
        self.assertTrue(incomplete)
        self.assertFalse(passed)
        per, passed, incomplete = g3.tally(rows[:2], ["a1"], 2)
        self.assertTrue(passed and not incomplete)


class G4Tests(unittest.TestCase):
    def test_missing_reference_box_is_a_failure_with_reason(self):
        t = {"name": "order_a1_v1", "screen": "order",
             "truth": {"amount": [0, 0, 10, 10], "address": [0, 20, 10, 30]}}
        got = g4.measure(t, [{"label": "amount", "box": [0, 0, 10, 10], "confidence": 0.9},
                             {"label": "confirm button", "box": [0, 40, 10, 50]}])
        self.assertEqual([e["label"] for e in got], list(g4.LABELS))
        self.assertEqual(got[0]["iou"], 1.0)
        self.assertEqual(got[1]["reason"], "the channel returned no region")
        self.assertEqual(got[2]["iou"], 0.0)
        self.assertIn("no reference box", got[2]["reason"])

    def test_fails_when_n_is_short(self):
        good = [{"iou": 0.9}] * 6
        self.assertTrue(g4.verdict(good, 6)[0])
        self.assertFalse(g4.verdict(good[:3], 6)[0])     # e.g. a capture lost to an API error


class ThresholdTests(unittest.TestCase):
    def test_two_of_three(self):
        self.assertEqual([g3.needed(n) for n in (1, 2, 3, 4, 5)], [1, 2, 2, 3, 4])

    def test_gpu_item_is_omitted(self):
        self.assertTrue(run_gate.blockers(("gpu",)))
        self.assertEqual(run_gate.mark({"pass": None}), "omitted")

    def test_crash_result_follows_the_contract(self):
        r = run_gate.crashed(1, "Traceback ...", "10 of 10")
        self.assertEqual((r["pass"], r["threshold"], r["n"]), (False, "10 of 10", 0))
        self.assertIn("exit 1", r["metric"])


if __name__ == "__main__":
    unittest.main()
