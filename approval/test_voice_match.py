"""F7: English number parsing and voice-vs-pixels matching (amounts in cents)."""

import unittest

from .voice_match import (words_to_int, amount_matches, amount_check, address_matches,
                          heard_amount, name_of, voice_matches)


class EnglishNumberTests(unittest.TestCase):
    def test_demo_amounts(self):
        self.assertEqual(words_to_int("twelve hundred forty dollars"), 1240)
        self.assertEqual(words_to_int("one thousand two hundred forty"), 1240)
        self.assertEqual(words_to_int("one thousand two hundred and forty"), 1240)
        self.assertEqual(words_to_int("a thousand two hundred forty"), 1240)
        self.assertEqual(words_to_int("fifteen hundred dollars"), 1500)

    def test_range(self):
        self.assertEqual(words_to_int("twenty"), 20)
        self.assertEqual(words_to_int("two hundred thirty-four"), 234)
        self.assertEqual(words_to_int("a hundred"), 100)
        self.assertEqual(words_to_int("one thousand"), 1000)
        self.assertEqual(words_to_int("five hundred thousand"), 500000)
        self.assertEqual(words_to_int("ninety nine"), 99)

    def test_case_and_noise(self):
        self.assertEqual(words_to_int("Twelve Hundred Forty"), 1240)
        self.assertEqual(words_to_int("that's twelve hundred forty US dollars"), 1240)

    def test_digits_with_thousands_separators(self):
        # what a transcriber may write instead of words
        for said in ("1,240", "1240.00", "$1,240", "$1,240.00 dollars", "1240", "1 240", "USD 1,240"):
            self.assertEqual(words_to_int(said), 1240, said)

    def test_cents_other_than_zero_are_not_whole_dollars(self):
        # a doubt is a "no": 1,240.50 never reads as 1,240
        for said in ("1,240.50", "$1240.99"):
            self.assertIsNone(words_to_int(said), said)

    def test_millions(self):
        self.assertEqual(words_to_int("one million two hundred thousand"), 1200000)
        self.assertEqual(words_to_int("two million"), 2000000)
        self.assertEqual(words_to_int("1,200,000 dollars"), 1200000)
        self.assertEqual(words_to_int("three million forty-five thousand six hundred"), 3045600)

    def test_one_well_formed_phrase_only(self):
        # two separate numbers are not one amount, even if the sum would match
        self.assertIsNone(words_to_int("five dollars, then twelve hundred thirty five"))
        self.assertIsNone(words_to_int("twelve hundred forty or fifteen hundred"))
        # malformed
        for said in ("forty twelve hundred", "hundred forty", "twelve forty", "thousand thousand",
                     "million", "twenty twelve", "five thousand 1240", "twelve hundred thousand",
                     "one two four zero"):
            self.assertIsNone(words_to_int(said), said)
        # the article "a" is not a second number
        self.assertEqual(words_to_int("a total of twelve hundred forty dollars"), 1240)

    def test_not_a_number(self):
        self.assertIsNone(words_to_int("Larkspur Market"))
        self.assertIsNone(words_to_int(""))

    def test_street_address_is_not_a_number(self):
        # an address in digits or in words is dropped, never read as the amount
        self.assertIsNone(words_to_int("120 Harbor Road, Unit 4"))
        self.assertIsNone(words_to_int("one twenty Harbor Road unit four"))
        self.assertEqual(words_to_int("twelve hundred forty, 88 Mill St"), 1240)


class MatchTests(unittest.TestCase):
    AMOUNT = 124000                    # cents: USD 1,240.00
    ADDRESS = "Larkspur Market · 120 Harbor Road, Unit 4, Riverton"
    GOOD = "Twelve hundred forty dollars, ship to Larkspur Market"

    def test_amount_matches(self):
        self.assertTrue(amount_matches(self.GOOD, self.AMOUNT))
        self.assertFalse(amount_matches("fifteen hundred dollars, ship to Larkspur Market",
                                        self.AMOUNT))
        self.assertEqual(heard_amount(self.GOOD, self.ADDRESS), (124000, ""))

    def test_cents_on_screen_need_cents_spoken(self):
        # whole dollars only: USD 1,240.50 on screen is never matched by "twelve hundred forty"
        self.assertFalse(amount_matches(self.GOOD, 124050))

    def test_destination_name_matches(self):
        self.assertTrue(address_matches(self.GOOD, self.ADDRESS))
        self.assertTrue(address_matches("ship to larkspur market", self.ADDRESS))
        self.assertFalse(address_matches("twelve hundred forty dollars, ship to Dock 9 Storage",
                                         self.ADDRESS))
        # whole words, in order: a shorter or reordered name is not the same destination
        self.assertFalse(address_matches("ship to Larkspur", self.ADDRESS))
        self.assertFalse(address_matches("Market Larkspur", self.ADDRESS))

    def test_name_read_with_a_label_and_no_separator(self):
        # the reader may join the label, the name and the address on one line
        pixels = "SHIP TO Larkspur Market 120 Harbor Road, Unit 4, Riverton"
        self.assertEqual(name_of(pixels), "Larkspur Market")
        self.assertTrue(voice_matches(self.GOOD, self.AMOUNT, pixels)[0])

    def test_negation_rejects(self):
        for said in ("no, twelve hundred forty dollars, ship to Larkspur Market",
                     "don't confirm twelve hundred forty dollars, ship to Larkspur Market",
                     "dont ship twelve hundred forty dollars to Larkspur Market",
                     "do not ship, twelve hundred forty dollars, Larkspur Market",
                     "cancel, twelve hundred forty dollars, ship to Larkspur Market",
                     "twelve hundred forty dollars, ship to Larkspur Market, actually not",
                     "never twelve hundred forty dollars, ship to Larkspur Market",
                     "stop, twelve hundred forty dollars, ship to Larkspur Market",
                     "wait, twelve hundred forty dollars, ship to Larkspur Market"):
            ok, detail = voice_matches(said, self.AMOUNT, self.ADDRESS)
            self.assertFalse(ok, said)
            self.assertIn("negation", detail)

    def test_complement_inside_an_address_is_not_a_number(self):
        said = "twelve hundred forty dollars, ship to Larkspur Market, 120 Harbor Road, Unit 4"
        self.assertTrue(voice_matches(said, self.AMOUNT, self.ADDRESS)[0])
        said = ("twelve hundred forty dollars, ship to Larkspur Market, one twenty Harbor Road "
                "unit four")
        self.assertTrue(voice_matches(said, self.AMOUNT, self.ADDRESS)[0])

    def test_two_amounts_never_sum(self):
        ok, _detail = voice_matches("five dollars, then twelve hundred thirty five, Larkspur Market",
                                    self.AMOUNT, self.ADDRESS)
        self.assertFalse(ok)
        self.assertFalse(voice_matches("forty twelve hundred dollars, ship to Larkspur Market",
                                       self.AMOUNT, self.ADDRESS)[0])

    def test_address_digits_do_not_join_the_amount(self):
        # review of cebf0f4 (ported): an address number next to the amount is never joined
        for said in ("Larkspur Market 120 Harbor Road 1,240",
                     "Larkspur Market, 120 Harbor Road, 1,240 dollars",
                     "1,240 dollars, Larkspur Market 120 Harbor Rd Unit 4",
                     "Larkspur Market 120 harbor road unit 4 1 240"):
            self.assertTrue(voice_matches(said, self.AMOUNT, self.ADDRESS)[0], said)
        self.assertEqual(words_to_int("120 Harbor Road 1,240"), 1240)
        # still strict: another number next to it is a second number
        self.assertFalse(voice_matches("Larkspur Market 120 Harbor Road 5 1,240",
                                       self.AMOUNT, self.ADDRESS)[0])

    def test_address_numbers_never_change_the_amount(self):
        for said in ("twelve hundred forty dollars, ship to Larkspur Market, 120 Harbor Road",
                     "twelve hundred forty dollars, ship to Larkspur Market, 120 Harbor Rd., Unit 4",
                     "twelve hundred forty dollars, ship to Larkspur Market, one twenty Harbor "
                     "Road unit four",
                     "twelve hundred forty to 120 Harbor Road, Larkspur Market",
                     "twelve hundred forty to one twenty Harbor Road, Larkspur Market",
                     "ship to Larkspur Market one twenty Harbor Road, twelve hundred forty dollars"):
            self.assertTrue(voice_matches(said, self.AMOUNT, self.ADDRESS)[0], said)
        # an address said in words never adds to or replaces the amount
        for said in ("eleven hundred dollars, one forty Harbor Road, Larkspur Market",
                     "twelve hundred forty Harbor Road, Larkspur Market"):
            self.assertFalse(voice_matches(said, self.AMOUNT, self.ADDRESS)[0], said)
        # the amount said after the name still counts when nothing came before
        self.assertTrue(voice_matches("ship to Larkspur Market, twelve hundred forty dollars",
                                      self.AMOUNT, self.ADDRESS)[0])

    def test_millions_and_out_of_range(self):
        self.assertTrue(voice_matches("one million two hundred thousand, ship to Larkspur Market",
                                      120_000_000, self.ADDRESS)[0])
        ok, _heard, why = amount_check("one billion, ship to Larkspur Market",
                                       100_000_000_000, self.ADDRESS)
        self.assertFalse(ok)
        self.assertIn("out of range", why)
        self.assertIn("out of range", voice_matches("x", 100_000_000_000, self.ADDRESS)[1])

    def test_still_matching(self):
        self.assertTrue(voice_matches(self.GOOD, self.AMOUNT, self.ADDRESS)[0])
        for said in ("$1,240, ship to larkspur market", "1240.00 dollars, ship to Larkspur Market",
                     "one thousand two hundred forty dollars, ship to Larkspur Market"):
            self.assertTrue(voice_matches(said, self.AMOUNT, self.ADDRESS)[0], said)

    def test_voice_mismatch_amount(self):
        ok, detail = voice_matches("fifteen hundred dollars, ship to Larkspur Market",
                                   self.AMOUNT, self.ADDRESS)
        self.assertFalse(ok)
        self.assertIn("amount", detail)

    def test_voice_mismatch_destination(self):
        ok, detail = voice_matches("twelve hundred forty dollars, ship to Dock 9 Storage",
                                   self.AMOUNT, self.ADDRESS)
        self.assertFalse(ok)
        self.assertIn("destination", detail)


if __name__ == "__main__":
    unittest.main()
