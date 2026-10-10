# Utility Bill Decoder — WTQ Build Track

Reads K-Electric, LESCO and IESCO electricity bill images and produces:

- **Level 1** — one guide-compliant JSON per bill → `output/level1.csv`
- **Level 2** — plain-English answers to customer questions → `output/level2.csv`

**Runtime:** Python 3.14 (works on 3.11+). Built spec-first — see `docs/` and `AGENTS.md`.

## How it works
```
image → preprocess (auto-rotate, resize)
      → LLM: read Level 1 fields as printed  → Python: normalize (numbers, CR→negative, dates, provider)
      → Python: cross-check sums/readings    → LLM: one re-read only if checks fail (values never auto-corrected)
      → LLM: read supporting facts (usage & billing history, rates, late-payment tiers)
      → Python: compute every number for Level 2 (averages, counts, %, differences, estimates)
      → LLM: answer all 12 questions for the bill in one call, grounded in bill + computed stats
      → csv module → output/level1.csv, output/level2.csv
```
The LLM is used only where it adds value — reading the image and writing English. Parsing, arithmetic,
validation and CSV formatting are deterministic Python. About 3 LLM calls per bill; responses are cached
in `.cache/` so re-runs are free.

## Setup
```bash
cd source
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # Windows: copy .env.example .env
# edit .env: set API_KEY (and MODEL_PROVIDER / MODEL_NAME if not using Gemini)
python -m decoder ping               # should print {"ok": true}
```

## Run
All commands from inside `source/`. Folder layout assumed: `../train/bills`, `../test/bills`, `../test/csv`.

```bash
# Training bills (no templates; uses the guide's sample questions, prints gold check for KESC_0008)
python -m decoder run --bills ../train/bills --out ../output_train

# Test bills: fills the provided templates → ../output/level1.csv and ../output/level2.csv
python -m decoder run --bills ../test/bills --csv ../test/csv --out ../output

# Check the result files against the templates (rows, columns, ids, no empty cells, valid JSON)
python -m decoder validate --csv ../test/csv --out ../output

# One bill, for the demo
python -m decoder show --bill ../test/bills/KESC_0002.png --question "How much of my bill is taxes?"

# Build the submission ZIP (output/ + source/, excludes .env and caches)
python -m decoder package --root .. --zip ../submission.zip

# Offline unit tests (no API key needed)
python -m unittest discover -s tests
```
Useful flags: `--level 1` (extraction only), `--only KESC_0002 LESCO_0008` (subset), `--workers 4`
(parallel bills; keep 1 on the Gemini free tier), `-v` (debug logs).
Per-bill details (raw reading, checks, facts, stats, answers) are written to `<out>/debug/<bill_id>.json`.

## Web UI (optional)
```bash
streamlit run app.py
```
- **Decode a bill:** upload an image → key amounts, charges/taxes tables, consistency checks, the exact Level 1 JSON,
  and a chat box to ask questions about that bill.
- **Batch:** generates and validates `level1.csv` / `level2.csv` from the templates, with download buttons.

The UI calls the same pipeline as the CLI; it adds no extra model logic.

## Accuracy on training bills
Gold files for all 5 training bills are in `examples/gold/` (KESC_0008 from the guide; the others written by hand
from the images). Every `run` prints a per-bill score: currently **18/18 fields on all 5 bills**.

## Configuration (`.env`)
| Variable | Meaning | Default |
|---|---|---|
| `MODEL_PROVIDER` | `google` or `anthropic` | `google` |
| `MODEL_NAME` | `gemini-3.1-flash-lite`, `gemini-3.5-flash-lite` or `claude-haiku-4-5` | per provider |
| `API_KEY` | provider API key | — |
| `MIN_INTERVAL_SEC` | min seconds between calls (rate limit) | 4.5 for google, 0 otherwise |
| `MAX_IMAGE_SIDE` | long side in px sent to the model | 2000 |
| `CACHE_DIR` | response cache | `.cache` |
| `FALLBACK_MODEL` | allowed model used when the main one is overloaded | the other Gemini Flash-Lite |
| `MAX_ATTEMPTS` | attempts per call | 8 |
| `FEWSHOT_IMAGE` | optional path to `KESC_0008.png` to send as a visual worked example | empty |

The code refuses any model not on the competition's allowed list.

## Project structure
```
source/
  AGENTS.md, CLAUDE.md      rules for coding agents
  docs/                     01 introduction · 02 specification · 03 clarifications · 04 plan · 05 tasks
  decoder/
    __main__.py             CLI (ping, run, show, validate, package)
  app.py                    Streamlit UI (single bill + batch)
    config.py               env settings + allowed-model guard
    llm.py                  Gemini / Claude client, JSON parsing, retries, pacing, cache
    preprocess.py           image orientation + resize
    schema.py               Level 1 field order and allowed types
    prompts.py              all prompts (L1, re-read, facts, L2) + QUESTION_HINTS
    normalize.py            as-printed strings → guide values
    validate.py             consistency checks that trigger a re-read
    stats.py                deterministic Level 2 numbers
    pipeline.py             per-bill orchestration with fallbacks
    io_csv.py               template read/write + output validation
    evaluate.py             gold comparison (numbers ±1)
    package.py              submission ZIP builder
  examples/gold/KESC_0008.json   worked example from the guide
  tests/test_offline.py          unit + offline end-to-end tests
```

## Error handling
- Up to 8 attempts with exponential backoff on API/JSON errors; on overload/quota errors (503/429) calls alternate
  with a fallback allowed model (`FALLBACK_MODEL`, default: the other Gemini Flash-Lite); pacing for rate limits.
  Successful replies are cached, so re-running the same command only redoes bills that failed.
- A failing bill never stops the run: Level 1 falls back to an all-null record of the right shape,
  Level 2 to an explicit "could not read" answer, so no CSV cell is empty.
- Config errors (missing key, disallowed model) stop early with a clear message.

## AI usage
- **LLM used by the solution:** Gemini 3.1 Flash-Lite (`gemini-3.1-flash-lite`) via Google AI Studio, with Gemini 3.5 Flash-Lite (`gemini-3.5-flash-lite`) as automatic fallback when 3.1 is overloaded. Both are on the allowed list.
  *(Change this line if you run with `claude-haiku-4-5` — it must match `.env.example`.)*
- **APIs:** Google Gen AI API (`google-genai` SDK). Anthropic Messages API supported in code (`anthropic` SDK) but only used if `MODEL_PROVIDER=anthropic`.
- **OCR / document services:** none.
- **Invoice/receipt extraction services:** none.
- **AI tools used to write the code:** Claude (Anthropic, claude.ai) for spec docs, architecture and code. *(Add any others you used, e.g. Antigravity.)*
