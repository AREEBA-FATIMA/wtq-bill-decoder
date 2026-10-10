# 02 — Specification

Source of truth: *WTQ Build Track Participant Guide* (sections 5–7). This file restates it as
testable requirements. IDs (`L1-x`, `L2-x`, `IO-x`, `NF-x`) are referenced by `05-tasks.md`.

## Inputs
- `bills/` folder of `.png` / `.jpg` images. `bill_id` = file name without extension.
- `csv/level1.csv` — columns `bill_id,json` (json empty), 10 rows.
- `csv/level2.csv` — columns `bill_id,question_id,question,answer` (answer empty), 120 rows (12 Qs × 10 bills).

## Level 1 — Extraction

**L1-1** Output exactly these keys, in this order, every time (null when unknown):
`provider, tariff, sanctioned_load_kw, bill_month, reading_date, issue_date, due_date,
previous_reading, current_reading, units_consumed, charges, total_charges, taxes, total_taxes,
current_bill, arrears, payable_within_due_date, payable_after_due_date`.

**L1-2** `provider` ∈ {`KE`,`LESCO`,`IESCO`}; derived from the file name (`KESC_*` → `KE`).

**L1-3** Values as printed — never recalculate, round or correct.

**L1-4** Amounts are JSON numbers in PKR: strip `Rs.`, commas, spaces. `CR` / parentheses / trailing `-` → negative. Subsidies negative.

**L1-5** Dates: `YYYY-MM-DD`; `bill_month`: `YYYY-MM`.

**L1-6** `null` for not printed / blank / grey box / unreadable. `[]` for empty lists. No guessing.

**L1-7** No PII: names, addresses, CNIC, account/reference/consumer/meter numbers.

**L1-8** `charges`: one entry per printed line in the charges section; skip blank and 0 lines; keep duplicates
(two `energy` slab lines = two entries). Types: `energy, fixed, fpa, quarterly_adjustment, surcharge, meter_rent, subsidy, other`.

**L1-9** `taxes`: one entry per line in the tax/government section; classify by **section**, not name.
Types: `gst, electricity_duty, income_tax, municipal_tax, other_tax`. Only a combined amount printed → `[]` + `total_taxes`.

**L1-10** `total_charges` / `total_taxes`: printed subtotals or null.

**L1-11** `arrears`: printed sign kept; null if blank.

**L1-12** `due_date` = last date without late surcharge. `payable_after_due_date` = **highest** late-payment amount.

**L1-13** Acceptance: training bill `KESC_0008` reproduces `examples/gold/KESC_0008.json` (numbers ±1, text/dates exact).

## Level 2 — Answers

**L2-1** One non-empty English answer per `level2.csv` row.
**L2-2** Numbers (averages, differences, counts, %, estimates) correct vs. the bill — computed in code.
**L2-3** Grounded only in the bill; no outside tariff data. Missing data → say so explicitly.
**L2-4** Estimates labelled "estimate" with the method stated.
**L2-5** Ambiguous question → state the interpretation used, or answer both.
**L2-6** No PII. English only (translate Urdu content).

## Output / IO

**IO-1** Generate `output/level1.csv` and `output/level2.csv` from the templates by code (no manual edits).
**IO-2** Keep column names, row order, `bill_id`, `question_id`, `question` unchanged.
**IO-3** UTF-8, CSV library quoting; Level 1 JSON on one line (quotes doubled by the CSV writer).
**IO-4** No empty `json` / `answer` cells — fallbacks if a call fails.

## Non-functional

**NF-1** Allowed LLM only, selected by `MODEL_PROVIDER` + `MODEL_NAME`; key from `API_KEY` in `.env`.
**NF-2** Python 3.11+; `requirements.txt` pinned.
**NF-3** Retries with backoff; per-call disk cache; rate pacing for the Gemini free tier (15 RPM).
**NF-4** One bill failing must not stop the run.
**NF-5** README with setup + exact run commands + AI usage section; `.env.example` with placeholders.
**NF-6** Submission ZIP ≤ 15 MB, no `.env` / keys / cache.
