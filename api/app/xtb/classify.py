import re
from dataclasses import dataclass
from decimal import Decimal

_NUMBER = r"(\d+(?:\.\d+)?)(?![\d.,])"
# Since 2026-10 XTB writes the ticker before the quantity ("OPEN BUY SXR8.DE 0.0614 @ 740.00"); a ticker has a letter.
_TICKER = r"(?:(?=\S*[A-Za-z])\S+\s+)?"
_OPEN = re.compile(rf"^OPEN\s+BUY\s+{_TICKER}{_NUMBER}(?:/{_NUMBER})?\s+@\s+{_NUMBER}", re.IGNORECASE)
_CLOSE = re.compile(rf"^CLOSE\s+BUY\s+{_TICKER}{_NUMBER}(?:/{_NUMBER})?\s+@\s+{_NUMBER}", re.IGNORECASE)
_TRANSFER = re.compile(r"Transfer\s+(in|out)\s+operation\s+on\s+account\s+with\s+id\s+(\d+)", re.IGNORECASE)

_BY_TYPE = {
    "stock purchase": "buy",
    "stock sale": "sell",
    "stock sell": "sell",
    "deposit": "deposit",
    "ike deposit": "deposit",
    "ikze deposit": "deposit",
    "withdrawal": "withdrawal",
    "dividend": "dividend",
    "divident": "dividend",
    "withholding tax": "withholding_tax",
    "free-funds interest": "interest",
    "free-funds interest tax": "interest_tax",
    "sec fee": "fee",
    "commission": "fee",
}


@dataclass(frozen=True)
class Classified:
    type: str
    quantity: Decimal | None = None
    price: Decimal | None = None
    counterparty_account: str | None = None


def classify(xtb_type: str, comment: str | None) -> Classified:
    """Maps an XTB cash-operation type and comment to our transaction type.

    Anything not recognised with certainty becomes "unknown" — it is stored and flagged, never dropped.
    """
    comment = (comment or "").strip()
    transfer = _TRANSFER.search(comment)
    if transfer:
        direction = "transfer_in" if transfer.group(1).lower() == "in" else "transfer_out"
        return Classified(direction, counterparty_account=transfer.group(2))

    mapped = _BY_TYPE.get((xtb_type or "").strip().lower(), "unknown")
    if mapped in ("buy", "sell"):
        match = (_OPEN if mapped == "buy" else _CLOSE).match(comment)
        if match is None:
            return Classified("unknown")
        return Classified(mapped, Decimal(match.group(1)), Decimal(match.group(3)))
    return Classified(mapped)
