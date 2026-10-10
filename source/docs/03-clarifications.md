# 03 — Clarifications & decisions

Ambiguities found in the guide and how we resolved them. Add new ones here as they come up.

| # | Question | Decision | Why |
|---|---|---|---|
| C1 | Who decides `provider`? | File-name prefix, not the model (`KESC`→`KE`). | Deterministic, guide defines the mapping. |
| C2 | Bill sums don't add up (e.g. charges ≠ subtotal). | Re-ask the model once with the mismatch; keep whichever reading has fewer failed checks. **Never** overwrite printed values with computed ones. | Rule L1-3 (as printed). Mismatch usually means a misread digit. |
| C3 | `units_consumed` ≠ current − previous. | Report printed value; mismatch only triggers a re-read. | Multipliers / meter changes exist. |
| C4 | Several late-payment amounts (KE 5% / 10%). | Take the maximum of all printed late amounts. | Guide 5.3 / 5.8. |
| C5 | Due date on KE shows both "Due Date" and LPS windows. | `due_date` = printed Due Date box (e.g. 21 Apr), not the end of the 5% window. | Worked example 5.7. |
| C6 | Model outputs numbers as strings with commas / `CR`. | Ask the model for amounts **as printed strings**; convert in Python. | Parsing is deterministic and testable. |
| C7 | Lines printed as 0 / blank. | Dropped from `charges` / `taxes`. | Guide 5.3. |
| C8 | TV fee / extra tax / further tax. | `other_tax` when in the government/tax section. | Guide 5.4.2 (section decides). |
| C9 | Opening balance / payments / adjustments (KE). | Not charges. Only "Previous Dues" maps to `arrears`. | Worked example: arrears = −0.53. |
| C10 | Level 2 "history" — includes current month? | Stats computed both ways; answer states which was used when it matters. | Guide 6.2 sample answer. |
| C11 | Gemini free tier is 15 RPM. | Pace calls (`MIN_INTERVAL_SEC`, default 4.5 s for Google). ~3 calls/bill → 30 calls total. | Avoid 429s. |
| C12 | Level 2 cost. | One LLM call answers all 12 questions for a bill (JSON keyed by question id). | 10 calls instead of 120. |
| C13 | Grey-box / unreadable values. | `null`. Prompt forbids guessing. | Correct nulls score as correct; invented values are penalized. |
| C14 | OCR (Tesseract)? | Not used. Vision LLM reads Urdu/tilted bills better; less setup. | Time budget. |
| C15 | LESCO/IESCO print no tax lines, only one "Taxes" figure. | `taxes: []`, figure → `total_taxes`. | Guide 5.3 combined-tax rule. |
| C16 | LESCO/IESCO charge lines. | "Total Electricity Charges" → `energy`; "Subsidies" → `subsidy` (negative); right-column "Total FPA" → `fpa`; "Net Electricity Charges" → `total_charges`. | Only lines printed in the charges breakdown. |
| C17 | FPA sits outside the Net Electricity Charges subtotal on IESCO. | Sum check also accepts `sum − (fpa + other)`. | Avoid false re-reads. |
| C18 | "NOT TO BE PAID" / L.P surcharge 0 cells. | `payable_after_due_date: null`; 0 cells ignored when a payable amount exists. | They are surcharges, not amounts. |
| C19 | Arrears printed as "39411 / 2" (amount / age). | First number → 39411. | Matches payable = current + arrears. |
| C20 | Several meter rows (net metering). | First row's previous/present/units. | Main import meter. |

## Open (fill at 12:30 once test questions are visible)
- Which of the 12 questions need a projection / estimate formula? → add to `decoder/prompts.py::QUESTION_HINTS` and, if needed, `decoder/stats.py`.
