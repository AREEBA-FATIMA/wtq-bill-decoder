"""Field-by-field comparison of a Level 1 record with a gold file (numbers +-1, text/dates exact)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .schema import L1_FIELDS


def _num_eq(a, b) -> bool:
    if a is None or b is None:
        return a is b
    try:
        return abs(float(a) - float(b)) <= 1
    except (TypeError, ValueError):
        return False


def _lines_eq(a: list, b: list) -> bool:
    if len(a or []) != len(b or []):
        return False
    pa = Counter((x["type"], round(float(x["amount"]))) for x in a or [])
    pb = Counter((x["type"], round(float(x["amount"]))) for x in b or [])
    return pa == pb


def compare(pred: dict, gold: dict) -> tuple[int, int, list[str]]:
    ok, diffs = 0, []
    for f in L1_FIELDS:
        p, g = pred.get(f), gold.get(f)
        if f in ("charges", "taxes"):
            same = _lines_eq(p, g)
        elif isinstance(g, (int, float)) or isinstance(p, (int, float)):
            same = _num_eq(p, g)
        else:
            same = p == g
        if same:
            ok += 1
        else:
            diffs.append(f"{f}: got {json.dumps(p)} expected {json.dumps(g)}")
    return ok, len(L1_FIELDS), diffs


def gold_for(bill_id: str, gold_dir: Path) -> dict | None:
    p = gold_dir / f"{bill_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
