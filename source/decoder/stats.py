"""Deterministic numbers for Level 2 answers. The LLM phrases; this module calculates."""

from __future__ import annotations

from statistics import mean

from .normalize import to_number

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]


def month_label(ym: str | None) -> str | None:
    try:
        y, m = ym.split("-")[:2]
        return f"{MONTH_NAMES[int(m) - 1]} {y}"
    except (AttributeError, ValueError, IndexError):
        return ym


def _r(x, nd: int = 2):
    return None if x is None else round(x, nd)


def _pct(part, whole):
    if part is None or not whole:
        return None
    return round(100 * part / whole, 2)


def _series_stats(series: list[dict], label: str) -> dict:
    units = [s["units"] for s in series]
    if not units:
        return {f"{label}_months": 0}
    hi = max(series, key=lambda s: s["units"])
    lo = min(series, key=lambda s: s["units"])
    out = {
        f"{label}_months": len(units),
        f"{label}_total_units": _r(sum(units)),
        f"{label}_average_units": _r(mean(units)),
        f"{label}_highest": {"month": month_label(hi["month"]), "units": hi["units"]},
        f"{label}_lowest": {"month": month_label(lo["month"]), "units": lo["units"]},
    }
    for threshold in (100, 200, 300):
        above = [s for s in series if s["units"] > threshold]
        out[f"{label}_months_above_{threshold}"] = {
            "count": len(above),
            "months": [f"{month_label(s['month'])} ({s['units']})" for s in above],
        }
    return out


def compute_stats(l1: dict, facts: dict) -> dict:
    stats: dict = {}
    units = l1.get("units_consumed")
    cb = l1.get("current_bill")
    tc, tt = l1.get("total_charges"), l1.get("total_taxes")
    charges, taxes = l1.get("charges") or [], l1.get("taxes") or []

    # --- composition of the bill
    by_type: dict[str, float] = {}
    for c in charges:
        by_type[c["type"]] = round(by_type.get(c["type"], 0) + c["amount"], 2)
    tax_by_type: dict[str, float] = {}
    for t in taxes:
        tax_by_type[t["type"]] = round(tax_by_type.get(t["type"], 0) + t["amount"], 2)
    taxes_total = tt if tt is not None else (round(sum(tax_by_type.values()), 2) if taxes else None)
    charges_total = tc if tc is not None else (round(sum(by_type.values()), 2) if charges else None)

    stats["charges_by_type_pkr"] = by_type
    stats["taxes_by_type_pkr"] = tax_by_type
    stats["taxes_share_of_current_bill_pct"] = _pct(taxes_total, cb)
    stats["charges_share_of_current_bill_pct"] = _pct(charges_total, cb)
    stats["energy_charges_pkr"] = by_type.get("energy")
    stats["energy_share_of_charges_pct"] = _pct(by_type.get("energy"), charges_total)
    stats["fixed_share_of_current_bill_pct"] = _pct(by_type.get("fixed"), cb)
    stats["adjustments_fpa_plus_qta_pkr"] = _r((by_type.get("fpa") or 0) + (by_type.get("quarterly_adjustment") or 0)) \
        if ("fpa" in by_type or "quarterly_adjustment" in by_type) else None

    # --- per unit
    if units:
        stats["average_cost_per_unit_current_bill_pkr"] = _r(cb / units) if cb is not None else None
        stats["average_cost_per_unit_charges_only_pkr"] = _r(charges_total / units) if charges_total is not None else None
        stats["energy_cost_per_unit_pkr"] = _r(by_type["energy"] / units) if by_type.get("energy") else None
        stats["taxes_per_unit_pkr"] = _r(taxes_total / units) if taxes_total is not None else None
    prev, curr = l1.get("previous_reading"), l1.get("current_reading")
    if None not in (prev, curr):
        stats["reading_difference"] = _r(curr - prev)

    # --- payment timing
    within, after = l1.get("payable_within_due_date"), l1.get("payable_after_due_date")
    if None not in (within, after):
        stats["late_payment_extra_pkr_max"] = _r(after - within)
        stats["late_payment_extra_pct_max"] = _pct(after - within, within)
    tiers = []
    for t in facts.get("late_payment_tiers") or []:
        amt = to_number(t.get("amount_payable"))
        if amt is not None and within is not None:
            tiers.append({"label": t.get("label"), "amount_payable": amt, "extra_vs_on_time_pkr": _r(amt - within)})
    if tiers:
        stats["late_payment_tiers_vs_on_time"] = tiers
    arrears = l1.get("arrears")
    if arrears is not None:
        stats["arrears_is_credit"] = arrears < 0

    # --- usage history
    hist = []
    for h in facts.get("usage_history") or []:
        u = to_number(h.get("units"))
        if u is not None:
            hist.append({"month": h.get("month"), "units": u})
    hist.sort(key=lambda h: h["month"] or "")  # oldest first
    current_month = l1.get("bill_month")
    includes_current = bool(facts.get("usage_history_includes_current_month")) or (
        bool(hist) and current_month is not None and hist[-1]["month"] == current_month
    )
    previous_only = [h for h in hist if h["month"] != current_month] if current_month else (
        hist[:-1] if includes_current else hist)
    with_current = previous_only + ([{"month": current_month, "units": units}] if units is not None else [])

    stats["history_previous_months"] = [f"{month_label(h['month'])}: {h['units']}" for h in previous_only]
    stats.update(_series_stats(previous_only, "history_excl_current"))
    stats.update(_series_stats(with_current, "history_incl_current"))

    if units is not None and previous_only:
        last = previous_only[-1]
        stats["change_vs_previous_month"] = {
            "previous_month": month_label(last["month"]), "previous_units": last["units"],
            "difference_units": _r(units - last["units"]), "change_pct": _pct(units - last["units"], last["units"]),
        }
        avg = mean(h["units"] for h in previous_only)
        stats["current_vs_history_average"] = {
            "average_units": _r(avg), "difference_units": _r(units - avg), "change_pct": _pct(units - avg, avg),
        }
        if current_month:
            y, m = current_month.split("-")
            same = f"{int(y) - 1:04d}-{m}"
            match = [h for h in previous_only if h["month"] == same]
            if match:
                stats["change_vs_same_month_last_year"] = {
                    "month": month_label(same), "units": match[0]["units"],
                    "difference_units": _r(units - match[0]["units"]),
                    "change_pct": _pct(units - match[0]["units"], match[0]["units"]),
                }
        recent3 = previous_only[-3:]
        stats["average_last_3_previous_months"] = _r(mean(h["units"] for h in recent3))

    # --- simple estimates (labelled as estimates by the answer prompt)
    if units and cb is not None and with_current:
        avg_all = mean(h["units"] for h in with_current)
        cpu = cb / units
        stats["estimate_next_bill_if_usage_equals_average_pkr"] = {
            "method": "history average units (incl. current) x current average cost per unit",
            "average_units": _r(avg_all), "cost_per_unit": _r(cpu), "estimate_pkr": _r(avg_all * cpu),
        }
        stats["estimate_annual_cost_pkr"] = {
            "method": "sum of units over months shown (incl. current) x current cost per unit, scaled to 12 months",
            "estimate_pkr": _r(sum(h["units"] for h in with_current) * cpu * 12 / len(with_current)),
        }

    # --- billing history
    bills = []
    for b in facts.get("billing_history") or []:
        amt, paid = to_number(b.get("billed_amount")), to_number(b.get("payment"))
        bills.append({"month": b.get("month"), "billed": amt, "paid": paid, "pay_date": b.get("payment_date")})
    bills.sort(key=lambda b: b["month"] or "", reverse=True)  # newest first
    if bills:
        billed = [b["billed"] for b in bills if b["billed"] is not None]
        stats["billing_history_rows"] = bills
        if billed:
            stats["billing_history_average_billed_pkr"] = _r(mean(billed))
            stats["billing_history_total_billed_pkr"] = _r(sum(billed))
        if cb is not None and bills[0]["billed"] is not None:
            stats["current_bill_vs_last_billed_pkr"] = _r(cb - bills[0]["billed"])

    split = facts.get("printed_percent_split") or {}
    if any(v is not None for v in split.values()):
        stats["printed_percent_split"] = split
    return stats
