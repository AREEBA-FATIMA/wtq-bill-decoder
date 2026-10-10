# 04 — Technical plan

## Stack
| Layer | Choice |
|---|---|
| Runtime | Python 3.11+ (built/tested on 3.12/3.13) |
| LLM | Gemini 3.1 Flash-Lite (free, default) **or** Claude Haiku 4.5 — switch with `MODEL_PROVIDER` |
| SDKs | `google-genai`, `anthropic` |
| Validation | own deterministic checks (`validate.py`) |
| Images | `Pillow` — EXIF auto-rotate, resize to ≤ 2000 px long side, PNG |
| Reliability | own retry loop (8 attempts, backoff, fallback model on 503/429), SHA-256 disk cache in `.cache/` |
| Config | `python-dotenv` |
| CLI | `argparse` → `python -m decoder ...` |

## Pipeline (per bill)
```
image ──► preprocess ──► [LLM #1] L1 raw extraction (amounts as printed strings)
                           │
                           ▼
                     normalize (numbers, CR, dates, provider from file name, drop 0 lines)
                           │
                           ▼
                     validate (sums, readings, payable) ──fail──► [LLM #1b] re-read once with mismatch list
                           │                                       keep result with fewer failures
                           ▼
                     L1 JSON  ──► level1.csv
image ──► [LLM #2] facts: usage history, billing history, rates, LPS tiers, % split, notes
                           │
                           ▼
                     stats.py: averages, counts, min/max, %, differences, cost/unit, projections
                           │
                           ▼
          [LLM #3] answer all 12 questions (image + L1 + facts + stats) ──► level2.csv
```

## Modules (`source/decoder/`)
| File | Responsibility |
|---|---|
| `config.py` | Read env → `Settings` dataclass |
| `llm.py` | Provider switch, image parts, JSON parsing, retries, pacing, cache |
| `preprocess.py` | Load + orient + resize image → PNG bytes |
| `schema.py` | Field order, allowed types, empty template |
| `prompts.py` | L1, re-read, facts, L2 prompts; `QUESTION_HINTS` |
| `normalize.py` | Raw model output → guide-compliant L1 dict |
| `validate.py` | Cross-checks returning human-readable issues |
| `stats.py` | Deterministic Level 2 numbers |
| `pipeline.py` | Orchestrates one bill; fallbacks |
| `io_csv.py` | Read templates, write CSVs, validate outputs |
| `evaluate.py` | Compare L1 against `examples/gold/*.json` (±1 numbers) |
| `package.py` | Build the submission ZIP (excludes secrets/cache) |
| `__main__.py` | CLI: `run`, `show`, `validate`, `package` |

## Debug artefacts
`output/debug/<bill_id>.json` holds raw extraction, issues, facts, stats, answers — for review and the demo. Excluded from ZIP? **No** — small and useful, but `package` can skip with `--no-debug`.

## Risks
| Risk | Mitigation |
|---|---|
| Misread digits | Sum checks + one re-read |
| Rate limits | Pacing + cache + retries |
| Wrong L2 math | Numbers precomputed in `stats.py`; prompt says use them |
| Empty cells | Fallback template / fallback answer |
| Time | Docs + code delivered together; 12:30 only tune prompts/stats |
