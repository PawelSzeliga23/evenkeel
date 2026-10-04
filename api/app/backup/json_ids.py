"""Numbers kept inside JSON columns: instruments of saved scenarios, accounts of AI reviews and of the preferences.

`walk` visits every such number with the table it points at and may replace it, so the same code collects the
references on export and renumbers them on restore.
"""
from collections.abc import Callable
from typing import Any

Visit = Callable[[str, int], int]


def _target(target: dict[str, Any], visit: Visit) -> None:
    if target.get("instrument_id") is not None:
        target["instrument_id"] = visit("instruments", target["instrument_id"])


def scenario(row: dict[str, Any], visit: Visit) -> None:
    """`allocation` and `steps` of a saved scenario (app/scenarios/schemas.py)."""
    for share in row.get("allocation") or []:
        _target(share.get("target") or {}, visit)
    for step in row.get("steps") or []:
        if step.get("kind") == "replace":
            step["from_instrument_id"] = visit("instruments", step["from_instrument_id"])
            step["to_instrument_id"] = visit("instruments", step["to_instrument_id"])
        else:
            _target(step.get("target") or {}, visit)


def review(row: dict[str, Any], visit: Visit) -> None:
    row["account_ids"] = [visit("accounts", i) for i in row.get("account_ids") or []]


def preferences(prefs: dict[str, Any], visit: Visit) -> None:
    if prefs.get("accounts_fixed"):
        prefs["accounts_fixed"] = [visit("accounts", i) for i in prefs["accounts_fixed"]]


ROWS: dict[str, Callable[[dict[str, Any], Visit], None]] = {"scenarios": scenario, "ai_reviews": review}
