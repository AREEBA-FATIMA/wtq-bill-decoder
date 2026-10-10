"""Offline tests: no API key needed. Run: python -m unittest discover -s tests"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image  # noqa: E402

from decoder import prompts  # noqa: E402
from decoder.evaluate import compare  # noqa: E402
from decoder.io_csv import l1_to_cell, validate_outputs, write_csv  # noqa: E402
from decoder.normalize import normalize_l1, to_day_date, to_month, to_number  # noqa: E402
from decoder.pipeline import BillDecoder  # noqa: E402
from decoder.schema import L1_FIELDS  # noqa: E402
from decoder.stats import compute_stats  # noqa: E402
from decoder.validate import check_l1  # noqa: E402

GOLD = json.loads((Path(__file__).resolve().parent.parent / "examples/gold/KESC_0008.json").read_text())
RAW_KESC_0008 = prompts.WORKED_EXAMPLE["output"]
FACTS = {
    "usage_history": [{"month": f"2025-{m:02d}", "units": u} for m, u in
                      zip(range(4, 13), [141, 138, 197, 239, 203, 179, 173, 187, 124])]
    + [{"month": "2026-01", "units": 96}, {"month": "2026-02", "units": 88}, {"month": "2026-03", "units": 115},
       {"month": "2026-04", "units": 151}],
    "usage_history_includes_current_month": True,
    "billing_history": [{"month": "2026-03", "billed_amount": 2577.31, "payment": 2577},
                        {"month": "2026-02", "billed_amount": 2782.51, "payment": 2783}],
}


class FakeClient:
    def __init__(self):
        self.calls = 0
        self.cache_hits = 0

    def json_call(self, prompt, images=None, tag=""):
        self.calls += 1
        if tag.startswith("l1"):
            return RAW_KESC_0008
        if tag.startswith("facts"):
            return FACTS
        return {"answers": {"Q1": "Taxes are PKR 569.62."}}


class NormalizeTests(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(to_number("Rs. 19,964"), 19964)
        self.assertEqual(to_number("38209CR"), -38209)
        self.assertEqual(to_number("38,209 Cr"), -38209)
        self.assertEqual(to_number("-0.53"), -0.53)
        self.assertEqual(to_number("1,054.00"), 1054)
        self.assertEqual(to_number("(12.50)"), -12.5)
        self.assertIsNone(to_number(""))
        self.assertIsNone(to_number(None))
        self.assertEqual(to_number("3 kW"), 3)

    def test_dates(self):
        self.assertEqual(to_day_date("22nd Sep 2026"), "2026-09-22")
        self.assertEqual(to_day_date("03-Apr-26"), "2026-04-03")
        self.assertEqual(to_day_date("2026-04-21"), "2026-04-21")
        self.assertEqual(to_month("MAR 2026"), "2026-03")
        self.assertEqual(to_month("Apr-26"), "2026-04")
        self.assertEqual(to_month("MAR 26"), "2026-03")

    def test_worked_example_matches_gold(self):
        rec = normalize_l1(RAW_KESC_0008, "KESC_0008")
        self.assertEqual(list(rec), L1_FIELDS)
        ok, total, diffs = compare(rec, GOLD)
        self.assertEqual(ok, total, diffs)
        self.assertEqual(check_l1(rec), [])

    def test_zero_lines_dropped_and_subsidy_negative(self):
        raw = {"charges": [{"type": "energy", "amount": "0"}, {"type": "subsidy", "amount": "500"},
                           {"type": "weird", "amount": "10"}]}
        rec = normalize_l1(raw, "LESCO_9002")
        self.assertEqual(rec["provider"], "LESCO")
        self.assertEqual(rec["charges"], [{"type": "subsidy", "amount": -500}, {"type": "other", "amount": 10}])


class WapdaTests(unittest.TestCase):
    def test_combined_tax_not_a_charge(self):
        raw = {"charges": [{"type": "energy", "amount": "17,367.77"}, {"type": "other", "amount": "3,358.23"}],
               "total_taxes": "3,358.23", "taxes": [], "payable_within_due_date": "54770CR",
               "late_payment_amounts": ["0", "0"], "payable_after_due_date": "NOT TO BE PAID", "arrears": "39411 / 2"}
        rec = normalize_l1(raw, "LESCO_0005")
        self.assertEqual(rec["charges"], [{"type": "energy", "amount": 17367.77}])
        self.assertEqual(rec["payable_within_due_date"], -54770)
        self.assertIsNone(rec["payable_after_due_date"])
        self.assertEqual(rec["arrears"], 39411)


class TestBillFixes(unittest.TestCase):
    """Synthetic numbers only (no test-bill values)."""

    def test_tax_cell_copied_from_current_bill(self):
        raw = {"charges": [{"type": "energy", "amount": "10000"}], "total_charges": "10000", "taxes": [],
               "total_taxes": "12000", "current_bill": "12000"}
        self.assertEqual(normalize_l1(raw, "IESCO_9001")["total_taxes"], 2000)

    def test_lesco_fpa_outside_current_bill_ok(self):
        rec = {"total_charges": 900.0, "total_taxes": 200.0, "current_bill": 980.0, "arrears": None,
               "payable_within_due_date": 1100, "payable_after_due_date": 1150, "due_date": "2026-01-15",
               "charges": [{"type": "energy", "amount": 900.0}], "taxes": [{"type": "gst", "amount": 200.0}]}
        self.assertEqual(check_l1(rec), [])


class ItemisedLescoTests(unittest.TestCase):
    def test_total_fpa_not_double_counted(self):
        # Total FPA 120 = FPA line 100 + GST on FPA 18 + ED on FPA 2 (synthetic)
        raw = {"charges": [{"label": "COST OF ELECTRICITY", "type": "energy", "amount": "500"},
                           {"label": "METER RENT", "type": "meter_rent", "amount": "100"},
                           {"label": "F.C SURCHARGE", "type": "surcharge", "amount": "20"},
                           {"label": "FIXED CHARGES", "type": "fixed", "amount": "300"},
                           {"label": "TOTAL FPA", "type": "fpa", "amount": "120"}],
               "total_charges": "920",
               "taxes": [{"label": "GST", "type": "gst", "amount": "90"},
                         {"label": "GST ON FPA", "type": "gst", "amount": "18"},
                         {"label": "ED ON FPA", "type": "electricity_duty", "amount": "2"}],
               "total_taxes": "110"}
        rec = normalize_l1(raw, "LESCO_9001")
        self.assertEqual([c["type"] for c in rec["charges"]], ["energy", "fpa", "surcharge", "fixed"])
        self.assertEqual(sum(c["amount"] for c in rec["charges"]), 920)


class ValidateTests(unittest.TestCase):
    def test_detects_sum_mismatch(self):
        rec = dict(GOLD, total_charges=2000)
        self.assertTrue(any("charges lines sum" in i for i in check_l1(rec)))


class StatsTests(unittest.TestCase):
    def test_sample_answers_numbers(self):
        st = compute_stats(GOLD, FACTS)
        self.assertEqual(st["taxes_share_of_current_bill_pct"], 16.61)
        self.assertEqual(st["history_excl_current_months"], 12)
        self.assertEqual(st["history_excl_current_months_above_200"]["count"], 2)
        self.assertEqual(st["history_incl_current_months_above_200"]["count"], 2)
        self.assertEqual(st["late_payment_extra_pkr_max"], 286)


class CsvAndPipelineTests(unittest.TestCase):
    def test_end_to_end_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            Image.new("RGB", (800, 1100), "white").save(tmp / "KESC_0008.png")
            dec = BillDecoder(FakeClient())
            res = dec.process(tmp / "KESC_0008.png", [("Q1", "How much is tax?"), ("Q2", "Other?")])
            self.assertEqual(compare(res.l1, GOLD)[0], len(L1_FIELDS))
            self.assertTrue(res.answers["Q2"])  # fallback, never empty

            out = tmp / "out"
            write_csv(out / "level1.csv", ["bill_id", "json"], [{"bill_id": "KESC_0008", "json": l1_to_cell(res.l1)}])
            write_csv(out / "level2.csv", ["bill_id", "question_id", "question", "answer"],
                      [{"bill_id": "KESC_0008", "question_id": q, "question": "x", "answer": a}
                       for q, a in res.answers.items()])
            self.assertEqual(validate_outputs(None, out), [])
            text = (out / "level1.csv").read_text(encoding="utf-8")
            self.assertIn('KESC_0008,"{""provider"":""KE"",""tariff"":""A1-R"",""sanctioned_load_kw"":3,', text)
            with (out / "level1.csv").open(newline="", encoding="utf-8") as f:
                row = list(csv.DictReader(f))[0]
            self.assertEqual(json.loads(row["json"])["payable_after_due_date"], 3716)


if __name__ == "__main__":
    unittest.main()
