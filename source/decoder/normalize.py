"""Turn the model's raw (as-printed) extraction into a guide-compliant Level 1 record."""

from __future__ import annotations

import re
from datetime import date

from dateutil import parser as dateparser

from .schema import CHARGE_TYPES, DAY_DATE_FIELDS, L1_FIELDS, NUMERIC_FIELDS, TAX_TYPES, provider_from_bill_id

_NULLISH = {"", "-", "--", "null", "none", "n/a", "na", "nil", "unreadable", "redacted", "hidden"}
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def to_number(value) -> int | float | None:
    """'Rs. 19,964' -> 19964, '38209CR' -> -38209, '(12.5)' -> -12.5, '1,054.00' -> 1054."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
    else:
        s = str(value).strip()
        if s.lower() in _NULLISH:
            return None
        neg = False
        if re.search(r"\bCR\b|CR$|Cr$", s, flags=re.IGNORECASE) or re.search(r"\d\s*CR", s, flags=re.IGNORECASE):
            neg = True
        if s.startswith("(") and s.endswith(")"):
            neg = True
        if re.search(r"\d-\s*$", s):
            neg = True
        s = re.sub(r"(?i)\b(rs\.?|pkr|kwh|kw|units?|cr)\b|rs\.?|cr", " ", s)
        s = s.replace(",", "").replace(" ", "")
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if not m:
            return None
        num = float(m.group())
        if neg:
            num = -abs(num)
    num = round(num, 2)
    return int(num) if num.is_integer() else num


def to_day_date(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if s.lower() in _NULLISH:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s, flags=re.IGNORECASE)
    try:
        d = dateparser.parse(s, dayfirst=True, default=date(2026, 1, 1))
    except (ValueError, OverflowError):
        return None
    return d.strftime("%Y-%m-%d")


def to_month(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if s.lower() in _NULLISH:
        return None
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return s
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s[:7]
    m = re.search(r"([A-Za-z]{3,9})[\s\-/'.,]*(\d{2,4})", s)
    if m and m.group(1)[:3].lower() in _MONTHS:
        year = int(m.group(2))
        year = year + 2000 if year < 100 else year
        return f"{year:04d}-{_MONTHS[m.group(1)[:3].lower()]:02d}"
    m = re.search(r"(\d{1,2})[\-/](\d{2,4})", s)
    if m:
        year = int(m.group(2))
        year = year + 2000 if year < 100 else year
        return f"{year:04d}-{int(m.group(1)):02d}"
    return None


def _lines(raw_lines, allowed: list[str], default: str, force_negative: str | None = None) -> list[dict]:
    out = []
    for line in raw_lines or []:
        if not isinstance(line, dict):
            continue
        amount = to_number(line.get("amount"))
        if amount is None or amount == 0:
            continue
        typ = str(line.get("type") or default).strip().lower()
        if typ not in allowed:
            typ = default
        if force_negative and typ == force_negative:
            amount = -abs(amount)
        out.append({"type": typ, "amount": amount})
    return out


def normalize_l1(raw: dict, bill_id: str) -> dict:
    """Map raw model output (strings as printed) to the final Level 1 dict in guide key order."""
    out: dict = {}
    for field in L1_FIELDS:
        val = raw.get(field)
        if field == "provider":
            out[field] = provider_from_bill_id(bill_id) or (str(val).upper() if val else None)
        elif field == "tariff":
            out[field] = None if val is None or str(val).strip().lower() in _NULLISH else str(val).strip()
        elif field == "bill_month":
            out[field] = to_month(val)
        elif field in DAY_DATE_FIELDS:
            out[field] = to_day_date(val)
        elif field == "charges":
            out[field] = _lines(val, CHARGE_TYPES, "other", force_negative="subsidy")
        elif field == "taxes":
            out[field] = _lines(val, TAX_TYPES, "other_tax")
        elif field in NUMERIC_FIELDS:
            out[field] = to_number(val)
        else:
            out[field] = val

    # A combined "Taxes" figure belongs in total_taxes, never in charges (LESCO/IESCO layout).
    tt = out.get("total_taxes")
    if tt is not None and not out["taxes"]:
        out["charges"] = [c for c in out["charges"] if not (c["type"] == "other" and abs(c["amount"] - tt) < 0.01)]

    # Guide 5.3: if several late-payment amounts are shown, use the highest.
    late = [to_number(v) for v in (raw.get("late_payment_amounts") or [])]
    late = [v for v in late + [out["payable_after_due_date"]] if v is not None]
    if out.get("payable_within_due_date"):  # a 0 next to a real payable amount is a surcharge cell, not an amount
        late = [v for v in late if v != 0]
    out["payable_after_due_date"] = max(late) if late else None
    return out
