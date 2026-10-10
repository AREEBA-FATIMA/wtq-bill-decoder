# CLAUDE.md

Follow `AGENTS.md` — it is the single source of rules for this repo. Read `docs/02-specification.md`
and `docs/03-clarifications.md` before editing extraction or answer logic.

Quick facts for Claude:
- Entry point: `python -m decoder` (`decoder/__main__.py`).
- Prompts live only in `decoder/prompts.py`. Per-question tuning goes in `QUESTION_HINTS`.
- Numbers for Level 2 come from `decoder/stats.py`; add a stat there rather than asking the model to calculate.
- Gold file for regression: `examples/gold/KESC_0008.json`.
- Run offline tests with `python -m unittest discover -s tests` after any change to `normalize.py`, `validate.py`, `stats.py` or `io_csv.py`.
