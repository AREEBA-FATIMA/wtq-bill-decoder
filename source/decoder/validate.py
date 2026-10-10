"""Consistency checks on a normalized Level 1 record.

These never change values. A non-empty issue list triggers one re-read by the model (see pipeline).
"""

from __future__ import annotations


def _close(a, b, tol: float) -> bool:
    return abs(float(a) - float(b)) <= tol


def check_l1(rec: dict) -> list[str]:
    issues: list[str] = []
    prev, curr, units = rec.get("previous_reading"), rec.get("current_reading"), rec.get("units_consumed")
    if None not in (prev, curr, units) and not _close(curr - prev, units, 1) and curr >= prev:
        issues.append(
            f"current_reading ({curr}) - previous_reading ({prev}) = {curr - prev}, but units_consumed is {units}. "
            "Re-read the meter readings and units (a meter multiplier is possible; if so keep printed values)."
        )

    charges = rec.get("charges") or []
    if rec.get("total_charges") is not None and charges:
        s = round(sum(c["amount"] for c in charges), 2)
        outside = round(sum(c["amount"] for c in charges if c["type"] in ("fpa", "other")), 2)
        # WAPDA bills print Total FPA / adjustments outside the Net Electricity Charges subtotal.
        if not (_close(s, rec["total_charges"], 2) or _close(s - outside, rec["total_charges"], 2)):
            issues.append(
                f"charges lines sum to {s} but total_charges is {rec['total_charges']}. "
                "A charge line may be missing, duplicated, misread, or belong to the tax section."
            )

    taxes = rec.get("taxes") or []
    if rec.get("total_taxes") is not None and taxes:
        s = round(sum(t["amount"] for t in taxes), 2)
        if not _close(s, rec["total_taxes"], 2):
            issues.append(
                f"tax lines sum to {s} but total_taxes is {rec['total_taxes']}. "
                "A tax line may be missing, duplicated, misread, or belong to the charges section."
            )

    tc, tt, cb = rec.get("total_charges"), rec.get("total_taxes"), rec.get("current_bill")
    within_ = rec.get("payable_within_due_date")
    arrears_ = rec.get("arrears") or 0
    # Some LESCO layouts exclude FPA from Current Bill; then charges + taxes = payable within due date - arrears.
    fpa_layout = within_ is not None and None not in (tc, tt) and _close(tc + tt, within_ - arrears_, 2)
    if None not in (tc, tt, cb) and not _close(tc + tt, cb, 2) and not fpa_layout:
        issues.append(
            f"total_charges ({tc}) + total_taxes ({tt}) = {round(tc + tt, 2)} but current_bill is {cb}. "
            "Check these three values (some bills add other items, then keep printed values)."
        )

    if rec.get("total_charges") is not None and not charges:
        issues.append(
            f"total_charges ({rec['total_charges']}) was found but the charges list is EMPTY. The individual charge "
            "lines above that total (cost of electricity / energy, fixed charges, FPA, QTR adjustment, F.C surcharge, "
            "meter rent, subsidy...) are printed on the bill: list every non-zero line."
        )
    if not charges and rec.get("total_charges") is None:
        issues.append("No charges and no total_charges were found; every bill prints its charges. Read them.")
    if tt is None and not taxes:
        issues.append(
            "No taxes and no total_taxes were found. If the bill prints any tax / government charges amount "
            "(even a single combined figure), put it in total_taxes."
        )

    within, after = rec.get("payable_within_due_date"), rec.get("payable_after_due_date")
    if rec.get("arrears") is None and None not in (within, cb) and abs(within - cb) > 300:
        issues.append(
            f"arrears is null but payable_within_due_date ({within}) differs from current_bill ({cb}) by "
            f"{round(within - cb, 2)}. Arrears / previous dues are probably printed (e.g. '39411 / 2' -> 39411)."
        )
    if None not in (within, after) and after < within:
        issues.append(
            f"payable_after_due_date ({after}) is lower than payable_within_due_date ({within}). Re-check both."
        )
    if within is None:
        issues.append("payable_within_due_date is missing; it is almost always printed prominently.")
    if rec.get("due_date") is None:
        issues.append("due_date is missing; it is almost always printed.")
    return issues
