# AGENTS.md — rules for any coding agent working on this repo

Project: **Utility Bill Decoder** (WTQ Build Track). Spec-driven: read `docs/` in order before changing code.

1. `docs/01-introduction.md` — goal and scoring
2. `docs/02-specification.md` — requirements (IDs L1-x, L2-x, IO-x, NF-x)
3. `docs/03-clarifications.md` — decisions on ambiguities
4. `docs/04-plan.md` — architecture and module map
5. `docs/05-tasks.md` — task list; tick tasks when done

## Hard rules (disqualification or score loss if broken)
- Call **only** these models: `claude-haiku-4-5`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gpt-4.1-mini`, `gpt-5-mini`.
- No invoice/receipt extraction services (Textract AnalyzeExpense, Azure prebuilt-invoice, Mindee).
- Never hardcode or commit API keys. Config comes from `.env` (see `.env.example`).
- Never output PII (names, addresses, CNIC, account/reference/consumer/meter numbers).
- Level 1 values are **as printed**. Do not compute replacement values; validation may only trigger a re-read.
- Output CSVs are produced by code only. Keep columns, row order, ids and questions unchanged.
- No cell may be empty: keep the fallbacks in `pipeline.py`.

## Working rules
- The LLM reads and writes language; Python does arithmetic, parsing and formatting.
- Keep modules single-purpose (see module map in `docs/04-plan.md`). No new dependencies unless pinned in `requirements.txt` and listed in README.
- Every prompt change: rerun `python -m decoder run --bills <train> --out <out>` and check the gold score for `KESC_0008` does not drop.
- Record any new ambiguity + decision in `docs/03-clarifications.md`.
- If you use an AI tool to write code, add it to README → *AI usage*.

## Commands
```bash
python -m decoder ping                                   # test API key
python -m decoder run --bills BILLS --out OUT            # training mode (no templates)
python -m decoder run --bills BILLS --csv CSV --out OUT  # test mode (fills templates)
python -m decoder show --bill BILL_IMAGE                 # one bill, for demo
python -m decoder validate --csv CSV --out OUT           # submission checks
python -m decoder package --zip ../submission.zip        # build ZIP
python -m unittest discover -s tests                     # offline tests
```
