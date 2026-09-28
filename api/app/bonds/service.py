"""Bond purchases as the API shows them (computed live for one day with the valuation's own functions)."""
import datetime as dt

from app.bonds import edo
from app.bonds.schemas import BondDetailOut, BondOut, PeriodOut
from app.models import Account, BondHolding
from app.valuation.engine import ZERO
from app.valuation.fixed_income import FLAG_RATE_ESTIMATED, Holding, payout_day, payout_per_bond
from app.valuation.service import FixedIncome


def _status(holding: Holding, schedule: list[edo.Period], day: dt.date) -> str:
    paid_on = payout_day(holding, schedule)
    if day < paid_on:
        return "active"
    return "redeemed" if paid_on < schedule[-1].end else "matured"


def bond_detail(stored: BondHolding, account: Account, fixed: FixedIncome, day: dt.date) -> BondDetailOut:
    holding = next(h for h in fixed.holdings if h.id == stored.id)
    schedule = edo.periods(holding.purchase_date, holding.series, fixed.cpi)
    status = _status(holding, schedule, day)
    paid_on = payout_day(holding, schedule)
    gross = edo.value(schedule, day)
    active = status == "active"
    quantity = holding.quantity
    flags = [FLAG_RATE_ESTIMATED] if active and edo.period_on(schedule, day).estimated else []
    if active:
        value = quantity * edo.net_value(gross, holding.taxed)
    elif day == paid_on:  # the payout day: like the daily valuation, the payout is still on the account
        value = quantity * payout_per_bond(holding, schedule)
    else:
        value = ZERO.quantize(edo.CENT)
    bond = BondOut(
        id=stored.id, account_id=account.id, account_name=account.name, bond_type=stored.bond_type,
        series=stored.series, quantity=quantity, purchase_date=stored.purchase_date, redeemed_at=stored.redeemed_at,
        maturity_date=schedule[-1].end, note=stored.note, status=status,
        value_pln=value, flags=flags,
    )
    redemption = (quantity * edo.redemption_value(gross, holding.series.early_redemption_fee, holding.taxed)
                  if active else None)
    return BondDetailOut(
        bond=bond, value_per_bond=gross, redemption_today_pln=redemption,
        periods=[PeriodOut(number=p.number, start=p.start, end=p.end, rate=p.rate, estimated=p.estimated)
                 for p in schedule],
    )
