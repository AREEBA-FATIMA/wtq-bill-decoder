"""Read the provided CSV templates and write completed result files (guide section 7.1-7.2)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .schema import L1_FIELDS

L1_COLUMNS = ["bill_id", "json"]
L2_COLUMNS = ["bill_id", "question_id", "question", "answer"]


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)


def l1_to_cell(rec: dict) -> str:
    """One-line JSON; the csv writer doubles the quotes."""
    ordered = {k: rec.get(k) for k in L1_FIELDS}
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))


def questions_by_bill(l2_rows: list[dict]) -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {}
    for r in l2_rows:
        out.setdefault(r["bill_id"], []).append((r["question_id"], r["question"]))
    return out


def validate_outputs(csv_dir: Path | None, out_dir: Path) -> list[str]:
    """Return a list of problems; empty means the outputs pass the guide's format checks."""
    problems: list[str] = []
    for name, cols, value_col in (("level1.csv", L1_COLUMNS, "json"), ("level2.csv", L2_COLUMNS, "answer")):
        out_path = out_dir / name
        if not out_path.exists():
            problems.append(f"{name}: missing in {out_dir}")
            continue
        fields, rows = read_csv(out_path)
        if fields != cols:
            problems.append(f"{name}: columns {fields} != {cols}")
        for i, r in enumerate(rows, start=2):
            if not (r.get(value_col) or "").strip():
                problems.append(f"{name} line {i}: empty {value_col}")
        if csv_dir and (csv_dir / name).exists():
            _, tpl = read_csv(csv_dir / name)
            if len(tpl) != len(rows):
                problems.append(f"{name}: {len(rows)} rows but template has {len(tpl)}")
            keys = [c for c in cols if c != value_col]
            for i, (a, b) in enumerate(zip(tpl, rows), start=2):
                if any(a.get(k) != b.get(k) for k in keys):
                    problems.append(f"{name} line {i}: id/question changed or row order differs")
                    break
        if name == "level1.csv":
            for i, r in enumerate(rows, start=2):
                try:
                    obj = json.loads(r["json"])
                except (json.JSONDecodeError, TypeError):
                    problems.append(f"level1.csv line {i}: json does not parse")
                    continue
                if list(obj) != L1_FIELDS:
                    problems.append(f"level1.csv line {i}: keys differ from schema")
    return problems
