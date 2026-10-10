"""CLI: python -m decoder {ping,run,show,validate,package}"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .config import ConfigError, load_settings
from .evaluate import compare, gold_for
from .io_csv import L1_COLUMNS, L2_COLUMNS, l1_to_cell, questions_by_bill, read_csv, validate_outputs, write_csv
from .pipeline import FALLBACK_ANSWER, BillDecoder, BillResult
from .preprocess import list_bills
from .prompts import SAMPLE_QA
from .schema import empty_l1

GOLD_DIR = Path(__file__).resolve().parent.parent / "examples" / "gold"
log = logging.getLogger("decoder")


def _decoder() -> BillDecoder:
    from .llm import LLMClient

    s = load_settings()
    log.info("Model: %s / %s", s.provider, s.model_name)
    return BillDecoder(LLMClient(s), s.max_image_side, s.fewshot_image)


def cmd_ping(_args) -> int:
    from .llm import LLMClient

    s = load_settings()
    print(f"{s.provider}/{s.model_name}: {LLMClient(s).ping()}")
    return 0


def cmd_run(args) -> int:
    bills_dir, out_dir = Path(args.bills), Path(args.out)
    images = {p.stem: p for p in list_bills(bills_dir)}
    if not images:
        print(f"No bill images found in {bills_dir}", file=sys.stderr)
        return 2

    if args.csv:  # test mode: fill the templates
        csv_dir = Path(args.csv)
        l1_fields, l1_rows = read_csv(csv_dir / "level1.csv")
        l2_fields, l2_rows = read_csv(csv_dir / "level2.csv") if (csv_dir / "level2.csv").exists() else (L2_COLUMNS, [])
    else:  # training mode: build rows from the images and use the guide's sample questions
        l1_fields, l2_fields = L1_COLUMNS, L2_COLUMNS
        l1_rows = [{"bill_id": b, "json": ""} for b in sorted(images)]
        l2_rows = [{"bill_id": b, "question_id": f"S{i}", "question": qa["question"], "answer": ""}
                   for b in sorted(images) for i, qa in enumerate(SAMPLE_QA, start=1)]
    if args.level == "1":
        l2_rows = []

    bill_ids = list(dict.fromkeys([r["bill_id"] for r in l1_rows] + [r["bill_id"] for r in l2_rows]))
    if args.only:
        bill_ids = [b for b in bill_ids if b in set(args.only)]
    qmap = questions_by_bill(l2_rows)
    decoder = _decoder()

    def work(bill_id: str) -> BillResult:
        path = images.get(bill_id)
        if path is None:
            log.error("%s: image not found in %s", bill_id, bills_dir)
            r = BillResult(bill_id=bill_id, l1=empty_l1(bill_id), errors=["image not found"])
            r.answers = {q: FALLBACK_ANSWER for q, _ in qmap.get(bill_id, [])}
            return r
        log.info("Processing %s", bill_id)
        return decoder.process(path, qmap.get(bill_id, []), level=args.level)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = {r.bill_id: r for r in pool.map(work, bill_ids)}

    debug_dir = out_dir / "debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    for r in results.values():
        (debug_dir / f"{r.bill_id}.json").write_text(json.dumps(r.debug(), ensure_ascii=False, indent=2),
                                                     encoding="utf-8")

    for row in l1_rows:
        res = results.get(row["bill_id"])
        row["json"] = l1_to_cell(res.l1 if res else empty_l1(row["bill_id"]))
    write_csv(out_dir / "level1.csv", l1_fields, l1_rows)
    if l2_rows:
        for row in l2_rows:
            res = results.get(row["bill_id"])
            row["answer"] = (res.answers.get(row["question_id"]) if res else None) or FALLBACK_ANSWER
        write_csv(out_dir / "level2.csv", l2_fields, l2_rows)

    print("\nSummary")
    for bid in bill_ids:
        r = results[bid]
        line = f"  {bid}: {len(r.issues)} check issue(s), {len(r.errors)} error(s)"
        gold = gold_for(bid, GOLD_DIR)
        if gold:
            ok, total, diffs = compare(r.l1, gold)
            line += f", gold {ok}/{total}"
            for d in diffs:
                line += f"\n      - {d}"
        for i in r.issues:
            line += f"\n      ! {i}"
        print(line)
    client = decoder.client
    print(f"\nLLM calls: {client.calls}, cache hits: {client.cache_hits}. Wrote {out_dir}/level1.csv"
          + (f" and {out_dir}/level2.csv" if l2_rows else "") + f"; details in {debug_dir}/")
    return 0


def cmd_show(args) -> int:
    path = Path(args.bill)
    questions = [(f"Q{i}", q) for i, q in enumerate(args.question or [qa["question"] for qa in SAMPLE_QA], start=1)]
    res = _decoder().process(path, questions)
    print("=== Level 1 JSON ===")
    print(json.dumps(res.l1, ensure_ascii=False, indent=2))
    if res.issues:
        print("\nChecks:", *res.issues, sep="\n  ! ")
    print("\n=== Level 2 answers ===")
    for qid, q in questions:
        print(f"\n{qid}. {q}\n  {res.answers.get(qid, FALLBACK_ANSWER)}")
    return 0


def cmd_templates(args) -> int:
    """Create level1.csv / level2.csv templates (guide section 4.2 format) from a bills folder + questions file."""
    bill_ids = sorted(p.stem for p in list_bills(Path(args.bills)))
    questions = [q.strip() for q in Path(args.questions).read_text(encoding="utf-8").splitlines() if q.strip()]
    out = Path(args.out)
    write_csv(out / "level1.csv", L1_COLUMNS, [{"bill_id": b, "json": ""} for b in bill_ids])
    write_csv(out / "level2.csv", L2_COLUMNS,
              [{"bill_id": b, "question_id": f"Q{i}", "question": q, "answer": ""}
               for b in bill_ids for i, q in enumerate(questions, start=1)])
    print(f"Wrote {out}/level1.csv ({len(bill_ids)} rows) and {out}/level2.csv ({len(bill_ids) * len(questions)} rows)")
    return 0


def cmd_validate(args) -> int:
    problems = validate_outputs(Path(args.csv) if args.csv else None, Path(args.out))
    if problems:
        print("Problems found:", *problems, sep="\n  - ")
        return 1
    print("OK: both CSV files pass the format checks.")
    return 0


def cmd_package(args) -> int:
    from .package import build_zip

    root = Path(args.root).resolve()
    size, warnings = build_zip(root, Path(args.zip).resolve(), include_debug=not args.no_debug)
    print(f"Wrote {args.zip} ({size / 1e6:.2f} MB)")
    for w in warnings:
        print("  WARNING:", w)
    return 1 if warnings else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m decoder", description="Utility Bill Decoder (WTQ Build Track)")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ping", help="test the API key with one tiny call")

    r = sub.add_parser("run", help="process a folder of bills and write level1.csv / level2.csv")
    r.add_argument("--bills", required=True, help="folder with bill images")
    r.add_argument("--csv", help="folder with level1.csv / level2.csv templates (omit for training mode)")
    r.add_argument("--out", required=True, help="output folder")
    r.add_argument("--level", choices=["all", "1"], default="all")
    r.add_argument("--workers", type=int, default=1, help="parallel bills (keep 1 on the Gemini free tier)")
    r.add_argument("--only", nargs="*", help="process only these bill_ids")

    s = sub.add_parser("show", help="decode one bill and print JSON + answers (demo)")
    s.add_argument("--bill", required=True)
    s.add_argument("--question", action="append", help="question to ask (repeatable)")

    t = sub.add_parser("templates", help="create level1/level2 CSV templates from a bills folder")
    t.add_argument("--bills", required=True)
    t.add_argument("--questions", default=str(Path(__file__).resolve().parent.parent / "examples" / "questions.txt"))
    t.add_argument("--out", required=True, help="folder to write the templates to (e.g. ../test/csv)")

    v = sub.add_parser("validate", help="check output CSVs against the templates")
    v.add_argument("--out", required=True)
    v.add_argument("--csv", help="template folder")

    p = sub.add_parser("package", help="build the submission ZIP")
    p.add_argument("--root", default="..", help="folder containing output/ and source/ (default: ..)")
    p.add_argument("--zip", default="../submission.zip")
    p.add_argument("--no-debug", action="store_true", help="leave output/debug out of the ZIP")

    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpcore", "google_genai", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        return {"ping": cmd_ping, "run": cmd_run, "show": cmd_show, "validate": cmd_validate, "templates": cmd_templates,
                "package": cmd_package}[args.cmd](args)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
