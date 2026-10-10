# 05 — Tasks

Status: `[x]` done · `[ ]` todo. Each task names the spec IDs it satisfies.

## Phase 0 — Setup (10:55–11:15)
- [x] T0.1 Folder layout, docs (intro, spec, clarifications, plan, tasks, AGENTS.md, CLAUDE.md)
- [ ] T0.2 Get API key, create `.env` from `.env.example`, `python -m decoder ping` succeeds (NF-1)
- [ ] T0.3 `pip install -r requirements.txt` in a venv (NF-2)

## Phase 1 — Level 1 (code done; verify 11:15–11:50)
- [x] T1.1 `preprocess.py` orientation + resize
- [x] T1.2 `llm.py` provider switch, retries, cache, pacing (NF-3)
- [x] T1.3 L1 prompt with all rules + provider hints (L1-1…L1-12)
- [x] T1.4 `normalize.py` numbers / CR / dates / provider / drop zero lines (L1-2, L1-4, L1-5, L1-8)
- [x] T1.5 `validate.py` + one re-read (C2)
- [x] T1.6 Gold check vs `KESC_0008` (L1-13)
- [x] T1.7 Run on 5 training bills (18/18 on all 5 gold files), eyeball each `output/debug/*.json` against its image; tune prompt hints

## Phase 2 — Level 2 (code done; verify 11:50–12:25)
- [x] T2.1 Facts extraction prompt (history, rates, LPS, split)
- [x] T2.2 `stats.py` deterministic numbers (L2-2)
- [x] T2.3 Answer prompt: grounded, estimates labelled, ambiguity stated, English (L2-3…L2-6)
- [x] T2.4 Fallback answer, never empty (IO-4)
- [ ] T2.5 Run sample questions on training bills; compare with guide 6.2

## Phase 2b — UI
- [x] T2.6 Streamlit UI: single-bill view + chat, batch CSV generation (`app.py`)

## Phase 3 — Test day (12:30–13:05)
- [ ] T3.1 Download `test/`; read the 12 questions
- [ ] T3.2 Add `QUESTION_HINTS` / stats for each question needing math
- [ ] T3.3 `python -m decoder run --bills ../test/bills --csv ../test/csv --out ../output`
- [ ] T3.4 `python -m decoder validate --csv ../test/csv --out ../output` passes (IO-1…IO-4)
- [ ] T3.5 Spot-check 3 bills in `output/debug/` vs images

## Phase 4 — Submit (13:05–13:20)
- [ ] T4.1 Update README AI-usage section (model actually used)
- [ ] T4.2 Optional demo recording ≤ 3 min (`python -m decoder show ...`)
- [ ] T4.3 `python -m decoder package --zip ../submission.zip`, open and inspect ZIP (NF-6)
- [ ] T4.4 Upload at https://build.womentechquest.com/submit — **once**
