# 01 — Introduction

## Problem
Pakistani electricity bills (K-Electric, LESCO, IESCO) are hard to read: tariff slabs, FPA/QTA
adjustments, many tax lines, Urdu text, and a different layout per provider. Bills arrive as
scans, screenshots or phone photos, sometimes tilted, with personal identifiers covered by grey boxes.

## Goal
An AI assistant that, for each bill image:

1. **Level 1 — Extraction:** returns one JSON object with non-identifying billing details
   (readings, dates, charges, taxes, payable amounts) in the exact schema of the WTQ guide.
2. **Level 2 — Explanation:** answers 12 customer questions per bill in plain English,
   grounded only in the bill, with correct calculations and labelled estimates.

## Users
- **Judges / scorers** — read `output/level1.csv` and `output/level2.csv`.
- **Bill payer (demo persona)** — uploads a bill, sees what they owe and why.

## Success criteria
| Area | Points | Our lever |
|---|---|---|
| Extraction accuracy | 30 | Vision LLM reads, Python normalizes + cross-checks sums, re-asks on mismatch |
| Answer quality | 30 | Python computes every number; LLM only phrases grounded answers |
| Engineering quality | 15 | Small modules, typed, retries, cache, never-empty fallbacks |
| AI design | 15 | LLM used only for reading & language; deterministic code for everything else |
| Completeness / reproducibility | 10 | One command, pinned deps, `.env.example`, `validate` + `package` commands |

## Constraints (hard)
- Only allowed LLMs: Claude Haiku 4.5, Gemini 3.5/3.1 Flash-Lite, GPT-4.1 mini, GPT-5 mini.
- No invoice/receipt extraction services (Textract AnalyzeExpense, Azure prebuilt-invoice, Mindee).
- Python 3.11+, pinned `requirements.txt`, no secrets in ZIP, ZIP ≤ 15 MB, **one submission only**.
- Deadline: test data 12:30, upload by 13:30 (aim 13:20).
