"""Level 1 output contract (guide section 5.1)."""

from __future__ import annotations

L1_FIELDS: list[str] = [
    "provider",
    "tariff",
    "sanctioned_load_kw",
    "bill_month",
    "reading_date",
    "issue_date",
    "due_date",
    "previous_reading",
    "current_reading",
    "units_consumed",
    "charges",
    "total_charges",
    "taxes",
    "total_taxes",
    "current_bill",
    "arrears",
    "payable_within_due_date",
    "payable_after_due_date",
]

NUMERIC_FIELDS = {
    "sanctioned_load_kw",
    "previous_reading",
    "current_reading",
    "units_consumed",
    "total_charges",
    "total_taxes",
    "current_bill",
    "arrears",
    "payable_within_due_date",
    "payable_after_due_date",
}
DAY_DATE_FIELDS = {"reading_date", "issue_date", "due_date"}

CHARGE_TYPES = ["energy", "fixed", "fpa", "quarterly_adjustment", "surcharge", "meter_rent", "subsidy", "other"]
TAX_TYPES = ["gst", "electricity_duty", "income_tax", "municipal_tax", "other_tax"]

PROVIDER_BY_PREFIX = {"KESC": "KE", "KE": "KE", "LESCO": "LESCO", "IESCO": "IESCO"}


def provider_from_bill_id(bill_id: str) -> str | None:
    prefix = bill_id.split("_")[0].upper()
    return PROVIDER_BY_PREFIX.get(prefix)


def empty_l1(bill_id: str) -> dict:
    """All-null record with the right shape — used when extraction fails."""
    out: dict = {f: None for f in L1_FIELDS}
    out["provider"] = provider_from_bill_id(bill_id)
    out["charges"] = []
    out["taxes"] = []
    return out
