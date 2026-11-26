import unittest

from app.ocr import parse_label

LABEL_1 = """SHOPPERS PHARMACY
123 Main St  Tel 555-0100
Rx# 4471923   Date: 2026-11-02
JANE DOE
AMOXICILLIN 500 MG CAPSULE
TAKE 1 CAPSULE BY MOUTH THREE TIMES A DAY
UNTIL FINISHED
Qty: 21   Refills: 0
Dr. A. Smith
"""

LABEL_2 = """Metformin 850mg tablets
Take two tablets twice daily with meals.
Quantity 120  2 refills
Prescriber: Dr Lee
"""

LABEL_3 = """ATORVASTATIN 20 MG TAB
TAKE ONE TABLET AT BEDTIME
QTY 30 NO REFILLS
"""

LABEL_4 = """IBUPROFEN 400 MG
Take 1 tablet every 6 hours as needed for pain
Qty 50
"""


class ParseTest(unittest.TestCase):
    def test_full_label(self):
        r = parse_label(LABEL_1)
        f = r["fields"]
        self.assertEqual((f["name"], f["strength"]), ("Amoxicillin", "500 mg"))
        self.assertEqual((f["dose_qty"], f["quantity"], f["refills_left"]), (1, 21, 0))
        self.assertEqual(f["rx_number"], "4471923")
        self.assertEqual(f["filled_on"], "2026-11-02")
        self.assertIn("Smith", f["prescriber"])
        self.assertIn("Pharmacy", f["pharmacy"].title())
        self.assertEqual(r["times"], ["08:00", "14:00", "20:00"])

    def test_twice_daily_word_numbers(self):
        r = parse_label(LABEL_2)
        f = r["fields"]
        self.assertEqual((f["name"], f["strength"], f["dose_qty"]), ("Metformin", "850 mg", 2))
        self.assertEqual((f["quantity"], f["refills_left"]), (120, 2))
        self.assertEqual(r["times"], ["08:00", "20:00"])

    def test_bedtime_no_refills(self):
        r = parse_label(LABEL_3)
        self.assertEqual(r["times"], ["21:00"])
        self.assertEqual((r["fields"]["refills_left"], r["fields"]["quantity"]), (0, 30))

    def test_as_needed_gets_no_schedule(self):
        r = parse_label(LABEL_4)
        self.assertEqual(r["times"], [])
        self.assertTrue(any("needed" in w for w in r["warnings"]))

    def test_garbage(self):
        r = parse_label("~~ %% blurry @@")
        self.assertEqual(r["times"], [])
        self.assertTrue(r["warnings"])


if __name__ == "__main__":
    unittest.main()
