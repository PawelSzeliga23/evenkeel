"""What selling a holding and taking the money out in PLN costs (plan 6d, pure functions): XTB's currency
conversion fee and a manual half-spread per instrument. Payout value = market value − exit costs."""
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.valuation.market_data import BASE_CURRENCY

ZERO = Decimal(0)
HUNDRED = Decimal(100)
CENT = Decimal("0.01")
XTB_FX_FEE = Decimal("0.005")  # XTB's currency conversion fee, 0.5 % of the converted amount


@dataclass(frozen=True)
class ExitRules:
    fee_accounts: frozenset[int] = frozenset()  # accounts whose broker charges the conversion fee (XTB)
    spreads: Mapping[int, Decimal] = field(default_factory=dict)  # instrument id → manual half-spread, percent

    def fx_fee(self, account_id: int, *currencies: str | None) -> Decimal:
        """The fraction of the value charged to convert it to PLN: XTB accounts, when any of the currencies (the
        instrument's quote currency, the account currency) is a foreign one."""
        if account_id in self.fee_accounts and any(c is not None and c != BASE_CURRENCY for c in currencies):
            return XTB_FX_FEE
        return ZERO

    def spread(self, instrument_id: int) -> Decimal:
        """The manual half-spread of the instrument as a fraction of the value (0 when none is set)."""
        return self.spreads.get(instrument_id, ZERO) / HUNDRED


def exit_part(value: Decimal, fraction: Decimal) -> Decimal:
    """`value × fraction` in grosze; nothing is charged on a value of zero or below."""
    if value <= 0 or not fraction:
        return ZERO.quantize(CENT)
    return (value * fraction).quantize(CENT, rounding=ROUND_HALF_UP)
