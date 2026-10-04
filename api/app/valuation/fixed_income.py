"""Daily valuation rows of treasury bonds and savings accounts (pure functions over preloaded inputs)."""
import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.bonds import edo
from app.savings.interest import savings_days
from app.valuation.engine import ONE_DAY, ZERO, Row, money

FLAG_RATE_ESTIMATED = "rate_estimated"


@dataclass(frozen=True)
class Holding:
    id: int
    account_id: int
    purchase_date: dt.date
    quantity: int
    redeemed_at: dt.date | None
    series: edo.Series
    taxed: bool  # a regular account: 19 % on interest; IKE / IKZE pay none


@dataclass(frozen=True)
class SavingsInput:
    id: int
    account_id: int
    capitalization: str
    taxed: bool
    balances: Sequence[tuple[dt.date, Decimal]]
    rates: Sequence[tuple[dt.date, Decimal]]
    flows: Sequence[tuple[dt.date, Decimal]] = ()


def payout_day(holding: Holding, schedule: Sequence[edo.Period]) -> dt.date:
    """Early redemption before maturity, otherwise the maturity day."""
    maturity = schedule[-1].end
    return holding.redeemed_at if holding.redeemed_at is not None and holding.redeemed_at < maturity else maturity


def payout_per_bond(holding: Holding, schedule: Sequence[edo.Period]) -> Decimal:
    day = payout_day(holding, schedule)
    gross = edo.value(schedule, day)
    if day < schedule[-1].end:
        return edo.redemption_value(gross, holding.series.early_redemption_fee, holding.taxed)
    return edo.net_value(gross, holding.taxed)


@dataclass(frozen=True)
class EarlyRedemption:
    day: dt.date
    fee: Decimal  # the fee charged on all the bonds
    value_drop: Decimal  # how much less the payout is than the value that day without the fee (fee less its tax)


def early_redemption(holding: Holding, cpi: Mapping[dt.date, Decimal]) -> EarlyRedemption | None:
    """The fee of a purchase redeemed before maturity; None for one held to maturity or still held."""
    schedule = edo.periods(holding.purchase_date, holding.series, cpi)
    day = payout_day(holding, schedule)
    if day >= schedule[-1].end:
        return None
    gross = edo.value(schedule, day)
    charged = min(holding.series.early_redemption_fee, max(gross - edo.NOMINAL, ZERO))
    quantity = Decimal(holding.quantity)
    drop = quantity * (edo.net_value(gross, holding.taxed) - payout_per_bond(holding, schedule))
    return EarlyRedemption(day, quantity * charged, drop)


def bond_rows(holdings: Iterable[Holding], cpi: Mapping[dt.date, Decimal], start: dt.date, end: dt.date) -> list[Row]:
    """Each purchase from its day: net value (the purchase is a deposit of 100 zł a bond); on the payout day the
    payout; the next day nothing, the payout leaving the account (a withdrawal at the start of that day, so a
    portfolio of bonds alone never shows the payout as a −100 % day)."""
    rows: list[Row] = []
    for holding in holdings:
        schedule = edo.periods(holding.purchase_date, holding.series, cpi)
        paid_on = payout_day(holding, schedule)
        quantity = Decimal(holding.quantity)
        cost = quantity * edo.NOMINAL
        payout = quantity * payout_per_bond(holding, schedule)
        day = max(holding.purchase_date, start)
        while day <= min(end, paid_on + ONE_DAY):
            flow = cost if day == holding.purchase_date else ZERO
            if day < paid_on:
                value = quantity * edo.net_value(edo.value(schedule, day), holding.taxed)
                flags = (FLAG_RATE_ESTIMATED,) if edo.period_on(schedule, day).estimated else ()
                rows.append(Row(holding.account_id, None, day, quantity, value, cost, flow, flags,
                                bond_holding_id=holding.id))
            elif day == paid_on:
                rows.append(Row(holding.account_id, None, day, quantity, payout, cost, flow,
                                bond_holding_id=holding.id))
            else:
                rows.append(Row(holding.account_id, None, day, ZERO, ZERO, ZERO, -payout, bond_holding_id=holding.id))
            day += ONE_DAY
    return rows


def savings_rows(accounts: Iterable[SavingsInput], start: dt.date, end: dt.date) -> list[Row]:
    """Each savings account from its first copied balance: the balance, the capital put in so far (cost) and the
    day's deposit or withdrawal."""
    rows: list[Row] = []
    for account in accounts:
        invested = ZERO
        for day in savings_days(account.balances, account.rates, account.capitalization, account.taxed, end, account.flows):
            invested += day.net_flow
            if day.day >= start:
                rows.append(Row(account.account_id, None, day.day, day.balance, money(day.balance), money(invested),
                                money(day.net_flow), savings_account_id=account.id))
    return rows


def day_view(rows: Sequence[Row], day: dt.date) -> tuple[Row, Decimal] | None:
    """One component's row on `day` and its change since the day before (net of that day's deposit); None when the
    component has no row that day or has been paid out."""
    by_day = {row.day: row for row in rows}
    today = by_day.get(day)
    if today is None or today.quantity == 0:
        return None
    before = by_day.get(day - ONE_DAY)
    return today, today.value_pln - today.net_flow_pln - (before.value_pln if before else ZERO)
