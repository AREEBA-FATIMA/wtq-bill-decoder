"""All prompts in one place. Tune here; rerun training bills after every change."""

from __future__ import annotations

import json

from .schema import CHARGE_TYPES, TAX_TYPES

# ---------------------------------------------------------------------------
# Level 1 — extraction
# ---------------------------------------------------------------------------

PROVIDER_HINTS = {
    "KE": """K-ELECTRIC layout hints:
- Header: "Bill Month: Apr-26", "Issue Date". Customer box: "Sanc Load", "Tariff" (e.g. A1-R).
- "Bill Calculation" table: "Reading Date" line at top. Charge lines (Fixed Charges, Variable Upto ... Units,
  Uniform Quarterly Adjustment, FCA <month>, Additional Surcharge (PHL), ...) end at the subtotal row
  "Electricity Charges" -> total_charges.
- Then tax lines (Electricity Duty, Sales Tax, MUCT (KMC), Income Tax, ...) end at "Taxes and Duties" -> total_taxes.
- "Electricity Charges for current month" -> current_bill.
- "Previous Dues" -> arrears (keep sign, e.g. -0.53). Opening Balance / Payments / Adjustment are NOT charges.
- "Amount Payable within Due Date" -> payable_within_due_date. "Due Date" box -> due_date.
- Late amounts: "Amount Payable from .. with 5% LPS" and "Amount Payable after .. with 10% LPS" -> put ALL in
  late_payment_amounts; payable_after_due_date = the last/highest.
- Meter readings in "Electricity You Have Used": Previous Reading, Current Reading, Units.
  If that table has SEVERAL rows (Energy - Off Peak / Peak / Import ...), previous_reading and current_reading
  are null, and units_consumed is the total in the "Current Month ... units" box.
  NEVER join numbers from different rows (e.g. 120 and 35 on two rows are two values, not 12035).""",
    "LESCO": """LESCO / IESCO (WAPDA-style) layout — exact mapping:
- Top-right panel: BILL MONTH (e.g. "JUL 2026" -> 2026-07), READING DATE, ISSUE DATE, DUE DATE.
  PAYABLE WITHIN DUE DATE -> payable_within_due_date (keep CR, e.g. "54770CR").
  L.P SURCHARGE row = surcharge amounts only (NOT payable amounts).
  PAYABLE AFTER DUE DATE row: "Upto/Till <date>" amount and "After <date>" amount -> put BOTH in late_payment_amounts.
  If it says "NOT TO BE PAID" (or nothing is printed) -> late_payment_amounts [] and payable_after_due_date null.
- CONSUMER DETAIL: SAN LOAD -> sanctioned_load_kw; TARIFF (e.g. A-1b(03)T, A-2a(04), A-1A(01)) -> tariff exactly.
- METER INFO: PREVIOUS READING, PRESENT READING, UNITS. If several meter rows are printed (net metering), use the FIRST row.
- BILL CHARGES BREAKDOWN, left column (this IS the charges section):
    "Total Electricity Charges"  -> charges entry, type energy
    "Subsidies"                  -> charges entry, type subsidy (negative) — only if a non-zero number is printed
    "Net Electricity Charges"    -> total_charges (the charges subtotal)
    "Taxes"                      -> ONE combined figure: taxes = [] and total_taxes = that figure
    "Current Bill"               -> current_bill
    "Grand Total"                -> (same as payable within due date; not a separate field)
- BILL CHARGES BREAKDOWN, right column:
    "Arrears" -> arrears (e.g. "39411 / 2" -> "39411"; printed 0 -> "0"; blank -> null; keep minus sign)
    "Total FPA" (non-zero)       -> charges entry, type fpa
    Installment / Adjustments / W.E Credit / Lock Open Credit (non-zero) -> charges entry, type other
- Percentages printed next to Net Electricity Charges / Taxes are not amounts.
- Net-metering bills may show negative (CR) units and amounts; keep those signs exactly.""",
}
PROVIDER_HINTS["IESCO"] = PROVIDER_HINTS["LESCO"]

L1_OUTPUT_SHAPE = {
    "tariff": "string exactly as printed, or null",
    "sanctioned_load_kw": "string as printed, or null",
    "bill_month": "YYYY-MM or null",
    "reading_date": "YYYY-MM-DD or null",
    "issue_date": "YYYY-MM-DD or null",
    "due_date": "YYYY-MM-DD or null",
    "previous_reading": "string as printed, or null",
    "current_reading": "string as printed, or null",
    "units_consumed": "string as printed, or null",
    "charges": [{"label": "line label as printed", "type": "|".join(CHARGE_TYPES), "amount": "string as printed"}],
    "total_charges": "string as printed, or null",
    "taxes": [{"label": "line label as printed", "type": "|".join(TAX_TYPES), "amount": "string as printed"}],
    "total_taxes": "string as printed, or null",
    "current_bill": "string as printed, or null",
    "arrears": "string as printed (keep sign / CR), or null",
    "payable_within_due_date": "string as printed, or null",
    "late_payment_amounts": ["every printed amount payable after the due date / with late surcharge"],
    "payable_after_due_date": "string as printed (highest late amount), or null",
    "notes": "short English note on anything unreadable or ambiguous (no personal data)",
}

L1_RULES = """RULES
1. Copy values exactly as printed. Do NOT calculate, round, fix or complete anything.
2. Amounts: give the printed text (e.g. "1,054.00", "38209CR", "-0.53"). Keep CR / minus signs.
3. Dates: convert to YYYY-MM-DD; bill month to YYYY-MM (e.g. "Apr-26" -> "2026-04", "22nd Sep 2026" -> "2026-09-22").
4. If a value is not printed, blank, covered by a grey box, or unreadable -> null. Never guess. Empty list -> [].
5. NEVER output names, addresses, CNIC, account, reference, consumer, contract or meter numbers.
6. charges: one entry per printed line in the CHARGES section, top to bottom. Skip blank lines and lines printed as 0.
   Keep separate entries when the same type appears twice (e.g. two energy slab lines). Do not include subtotal rows.
   Types: energy (cost of units / variable / energy charges), fixed, fpa (FPA or FCA), quarterly_adjustment (QTA / uniform
   quarterly adjustment), surcharge (e.g. Additional Surcharge (PHL), F.C Surcharge), meter_rent (meter / service rent),
   subsidy (government subsidy/relief, negative), other.
7. taxes: one entry per printed line in the TAX / GOVERNMENT section. Classify by the section a line sits in, not its name.
   Types: gst (sales tax incl. GST on FPA), electricity_duty (ED), income_tax, municipal_tax (e.g. MUCT (KMC)),
   other_tax (extra tax, further tax, TV fee, others). If only one combined tax amount is printed -> taxes [] and put it in total_taxes.
8. total_charges / total_taxes: the PRINTED subtotal rows only; null if no subtotal is printed.
   A printed subtotal almost always has its individual lines printed just above it: list those lines too.
   Never return an empty charges list when the charge lines are visible. If the bill prints only ONE combined
   tax / government charges figure, put that figure in total_taxes (taxes = []), never leave both empty.
9. due_date is the last date to pay WITHOUT late surcharge.
10. Read digits carefully, including on tilted photos and next to Urdu text."""

WORKED_EXAMPLE = {
    "bill": "KESC_0008 (K-Electric)",
    "output": {
        "tariff": "A1-R", "sanctioned_load_kw": "3", "bill_month": "2026-04", "reading_date": "2026-04-03",
        "issue_date": "2026-04-07", "due_date": "2026-04-21", "previous_reading": "8819", "current_reading": "8970",
        "units_consumed": "151",
        "charges": [
            {"label": "Fixed Charges", "type": "fixed", "amount": "900.00"},
            {"label": "Variable Upto 100 Units (Protected)", "type": "energy", "amount": "1,054.00"},
            {"label": "Variable Upto 200 Units (Protected)", "type": "energy", "amount": "663.51"},
            {"label": "Uniform Quarterly Adjustment", "type": "quarterly_adjustment", "amount": "52.91"},
            {"label": "FCA Feb-26", "type": "fpa", "amount": "125.27"},
            {"label": "Additional Surcharge (PHL)", "type": "surcharge", "amount": "64.93"},
        ],
        "total_charges": "2,860.62",
        "taxes": [
            {"label": "Electricity Duty", "type": "electricity_duty", "amount": "29.41"},
            {"label": "Sales Tax u/s 3(1)", "type": "gst", "amount": "520.21"},
            {"label": "MUCT (KMC)", "type": "municipal_tax", "amount": "20.00"},
        ],
        "total_taxes": "569.62", "current_bill": "3,430.24", "arrears": "-0.53",
        "payable_within_due_date": "3,430", "late_payment_amounts": ["3,574", "3,716"],
        "payable_after_due_date": "3,716", "notes": "",
    },
}


WORKED_EXAMPLE_WAPDA = {
    "bill": "IESCO_0004 (IESCO, same layout as LESCO)",
    "output": {
        "tariff": "A-1A(01)", "sanctioned_load_kw": "3", "bill_month": "2026-09", "reading_date": "2026-09-25",
        "issue_date": "2026-09-26", "due_date": "2026-10-08", "previous_reading": "9301", "current_reading": "9459",
        "units_consumed": "158",
        "charges": [
            {"label": "Total Electricity Charges", "type": "energy", "amount": "6102"},
            {"label": "Subsidies", "type": "subsidy", "amount": "3332"},
            {"label": "Total FPA", "type": "fpa", "amount": "267"},
        ],
        "total_charges": "2770", "taxes": [], "total_taxes": "498", "current_bill": "3267", "arrears": "0",
        "payable_within_due_date": "3535", "late_payment_amounts": ["3674", "3812"],
        "payable_after_due_date": "3812", "notes": "Taxes printed as one combined figure.",
    },
}


def l1_prompt(provider: str | None) -> str:
    hint = PROVIDER_HINTS.get(provider or "", "\n\n".join(PROVIDER_HINTS[p] for p in ("KE", "LESCO")))
    example = WORKED_EXAMPLE if provider == "KE" else WORKED_EXAMPLE_WAPDA
    return f"""Extract the billing details from this {provider or 'Pakistani'} electricity bill image.

{L1_RULES}

{hint}

WORKED EXAMPLE (different bill, for format only — never copy its values):
{json.dumps(example, ensure_ascii=False)}

Return ONE JSON object with exactly these keys:
{json.dumps(L1_OUTPUT_SHAPE, ensure_ascii=False, indent=1)}"""


def l1_reread_prompt(provider: str | None, previous: dict, issues: list[str]) -> str:
    return f"""{l1_prompt(provider)}

A previous reading of THIS bill produced:
{json.dumps(previous, ensure_ascii=False)}

Automatic checks found these inconsistencies:
- """ + "\n- ".join(issues) + """

Look at the image again and correct ONLY values that were misread, missed, duplicated or put in the wrong section.
If the printed numbers genuinely do not add up, keep them exactly as printed. Return the full JSON object again."""


# ---------------------------------------------------------------------------
# Level 2 — supporting facts (beyond the Level 1 schema)
# ---------------------------------------------------------------------------

FACTS_SHAPE = {
    "usage_history": [{"month": "YYYY-MM", "units": "number"}],
    "usage_history_includes_current_month": "true|false",
    "billing_history": [{"month": "YYYY-MM", "billed_amount": "number|null", "payment_date": "YYYY-MM-DD|null",
                         "payment": "number|null"}],
    "rate_lines": [{"label": "printed label", "units": "number|null", "rate": "number|null", "amount": "number|null"}],
    "late_payment_tiers": [{"label": "e.g. 22-24 Apr with 5% LPS", "surcharge": "number|null",
                            "amount_payable": "number|null"}],
    "printed_percent_split": {"energy_charges_pct": "number|null", "taxes_pct": "number|null"},
    "mdi_kw": "number|null",
    "number_of_months_billed": "number|null",
    "connection_or_installation_date": "YYYY-MM-DD|null",
    "meter_or_reading_status": "string|null",
    "protected_or_unprotected_status": "string|null",
    "other_printed_amounts": [{"label": "printed label", "amount": "number"}],
    "messages_in_english": ["short English translation/summary of notices on the bill (no personal data)"],
}


def facts_prompt(provider: str | None) -> str:
    return f"""This is a {provider or 'Pakistani'} electricity bill. Extract supporting facts that a customer might ask about.

- usage_history: every month in the consumption / usage history chart or table, oldest first, with the units printed
  (for bar charts read the number printed on/next to each bar). Mark whether the current month is included.
- billing_history: every row of billing / payment history (month, billed amount, payment date, amount paid).
- rate_lines: each charge line that shows units and a rate (e.g. slab lines, FCA rate, fixed charge rate).
- late_payment_tiers: each printed late-payment window with its surcharge and the amount payable.
- printed_percent_split: any printed percentage split between energy charges and taxes.
- other fields as available. Use numbers (no commas). Use null or [] when not printed or covered by a grey box.
- NEVER include names, addresses, CNIC, account, reference, consumer or meter numbers. Translate Urdu notices to English.

Return ONE JSON object with exactly these keys:
{json.dumps(FACTS_SHAPE, ensure_ascii=False, indent=1)}"""


# ---------------------------------------------------------------------------
# Level 2 — answers
# ---------------------------------------------------------------------------

# Filled at 12:30 after reading test/csv/level2.csv. Keyed by question_id ("Q1".."Q12").
QUESTION_HINTS: dict[str, str] = {
    "Q1": "Look at the image and data for net-metering signs: the words 'NET METERING' / 'Net Metering Benefit', "
          "customer type NM, separate Import/Export meter rows, negative or CR units in history, credit bills. "
          "Say net-metered or standard and name the exact evidence you saw.",
    "Q2": "Use last_12_months_incl_current.highest; also check history_excl_current_highest. If they differ, say "
          "which 12-month window you used (state your interpretation).",
    "Q3": "Use fpa entries in charges_by_type_pkr and printed_charge_lines labels (e.g. 'FCA Feb-26') plus any FPA "
          "note on the bill image (e.g. 'FPA FEB-26 @ 1.4235', Total FPA). Give amount and the month it relates to; "
          "if the month is not printed, say so.",
    "Q4": "Use late_payment_tiers_vs_on_time and late_payment_extra_pkr_max: each window/date, surcharge and total "
          "payable. If the bill says not to be paid / none printed, say so.",
    "Q5": "Use change_vs_same_month_last_year (units and %). If that month is not in the history, say so.",
    "Q6": "Use history_excl_current_average_units (previous months) and current_vs_history_average; mention the "
          "number of months averaged.",
    "Q7": "Use summer_jun_aug, winter_dec_feb and summer_minus_winter; list the months used from the history. If a "
          "season is missing or incomplete, say so.",
    "Q8": "Use payment_record: months shown, months with payment, unpaid or underpaid months, credit months. If the "
          "bill shows fewer than 12 months of payments (e.g. K-Electric shows 3), say only those months can be checked.",
    "Q9": "Use last_3_months_incl_current (and last_3_previous_months) with the monthly values and direction.",
    "Q10": "This is an ESTIMATE: give next_month_forecast.linear_trend_units as the trend estimate and also the "
           "same_month_last_year_units as a seasonal reference; state the method briefly.",
    "Q11": "ESTIMATE: use monthly_set_aside_from_billing_history_pkr when billing history has many months; otherwise "
           "estimate_annual_cost_pkr / 12. State the method and that it is an estimate.",
    "Q12": "ESTIMATE: use estimate_bill_if_same_units_as_last_month (state method; slabs and adjustments may differ). "
           "Mention last month's units. For net-metered/credit bills explain the limitation.",
}

L2_RULES = """ANSWER RULES
1. Use ONLY the bill image and the data below. No outside tariff, rate or policy information.
2. For every number use the precomputed values in COMPUTED_STATS when they apply; do not redo arithmetic yourself.
   Quote amounts as "PKR 1,234.56" and units as "151 units".
3. If the bill does not show something needed, say clearly that the bill does not show it, and answer what you can.
4. Label every estimate as an estimate and state how it was calculated in one short clause.
5. If a question has more than one reasonable meaning, say which meaning you used, or answer both briefly.
6. Never mention names, addresses, CNIC, account, reference, consumer or meter numbers.
7. Negative units or amounts usually mean net-metering export or a credit; explain that instead of treating them
   as normal consumption or charges.
8. Write in plain, friendly English (translate any Urdu). 1-4 sentences, specific, no filler, no markdown."""

SAMPLE_QA = [
    {"question": "How much of my bill is taxes?",
     "answer": "Taxes and duties total PKR 569.62 out of your current bill of PKR 3,430.24, or about 16.6%. The bill "
               "shows a split of 83.39% energy charges and 16.61% taxes. The tax lines are sales tax (PKR 520.21), "
               "electricity duty (PKR 29.41), and MUCT (KMC) (PKR 20.00)."},
    {"question": "How many months in my history went above 200 units?",
     "answer": "Two of the 12 previous months exceeded 200 units: July 2025 (239) and August 2025 (203). The current "
               "month used 151 units, so the count is two whether or not the current month is included."},
]


def l2_prompt(l1: dict, facts: dict, stats: dict, questions: list[tuple[str, str]]) -> str:
    q_block = []
    for qid, q in questions:
        hint = QUESTION_HINTS.get(qid)
        q_block.append({"id": qid, "question": q, **({"hint": hint} if hint else {})})
    return f"""You are helping a customer understand their electricity bill (image attached).

{L2_RULES}

EXAMPLE ANSWERS (another bill — style and level of detail only):
{json.dumps(SAMPLE_QA, ensure_ascii=False)}

EXTRACTED_BILL (Level 1, as printed):
{json.dumps(l1, ensure_ascii=False)}

SUPPORTING_FACTS:
{json.dumps(facts, ensure_ascii=False)}

COMPUTED_STATS (calculated by code from the values above — trust these numbers):
{json.dumps(stats, ensure_ascii=False)}

QUESTIONS:
{json.dumps(q_block, ensure_ascii=False, indent=1)}

Return ONE JSON object: {{"answers": {{"<id>": "<answer>", ...}}}} with an answer for every question id."""
