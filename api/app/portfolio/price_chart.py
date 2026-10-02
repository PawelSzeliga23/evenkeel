"""Wykres ceny (plan 7e): the instrument's closes in its own currency, with the position's operations on them."""
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from app.market.store import fx_on
from app.models import Account, Instrument, Price, Transaction
from app.portfolio.schemas import PriceChartOut, PriceMarkerOut, PricePointOut
from app.portfolio.service import amount_pln
from app.scoping import UserScope
from app.valuation.actions import resolve
from app.valuation.engine import ONE, Split
from app.valuation.service import _actions, local_day

LIMIT = 800
KINDS = ("buy", "sell", "dividend")
PRICE = Decimal("0.01")
FX_PRICE = Decimal("0.0001")  # as the lots' open_price_with_fx (engine PRICE_PLACES)


def thin(points: list[tuple[dt.date, Decimal]], limit: int = LIMIT) -> list[tuple[dt.date, Decimal]]:
    """Every n-th point so that at most `limit` remain, always with the first and the last."""
    if len(points) <= limit:
        return points
    step = -(-(len(points) - 1) // (limit - 1))
    kept = points[::step]
    return kept if kept[-1] == points[-1] else [*kept[:limit - 1], points[-1]]


def _factor(splits: list[Split], day: dt.date) -> Decimal:
    result = ONE
    for split in splits:
        if split.effective_date > day:
            result *= split.factor
    return result


def price_chart(scope: UserScope, account: Account, instrument: Instrument, start: dt.date | None) -> PriceChartOut:
    db = scope.db
    query = select(Price.date, Price.close).where(Price.instrument_id == instrument.id).order_by(Price.date)
    closes = [(day, _plain(close)) for day, close in db.execute(query)]
    shown = [(day, close) for day, close in closes if start is None or day >= start]

    splits, _ = resolve(_actions(db, scope.user.id, {instrument.id}))
    own = [s for s in splits if s.instrument_id == instrument.id]
    transactions = list(db.scalars(scope.transactions().where(
        Transaction.account_id == account.id, Transaction.instrument_id == instrument.id,
        Transaction.type.in_(KINDS))).unique())
    foreign = instrument.currency not in (None, account.currency)
    markers = []
    for t in sorted(transactions, key=lambda t: (t.occurred_at, t.id)):
        day = local_day(t.occurred_at)
        exact = amount_pln(db, t)
        amount = exact.quantize(PRICE, rounding=ROUND_HALF_UP)
        if t.type == "dividend":
            markers.append(PriceMarkerOut(date=day, kind="dividend", price=None, price_with_fx=None, quantity=None,
                                          amount_pln=amount))
            continue
        factor = _factor(own, day)
        quantity = _trim(abs(t.quantity) * factor) if t.quantity else None
        price = _trim(t.price / factor) if t.price is not None else _close_on(closes, day)
        with_fx = None
        if foreign and quantity:
            rate = fx_on(db, instrument.currency, day)
            with_fx = (abs(exact) / quantity / rate).quantize(FX_PRICE, rounding=ROUND_HALF_UP) if rate else None
        markers.append(PriceMarkerOut(date=day, kind=t.type, price=price, price_with_fx=with_fx, quantity=quantity,
                                      amount_pln=amount))
    buys = [m.date for m in markers if m.kind == "buy"]
    return PriceChartOut(currency=instrument.currency, points=[PricePointOut(date=d, close=c) for d, c in thin(shown)],
                         markers=markers, first_buy=min(buys) if buys else None)


def _close_on(closes: list[tuple[dt.date, Decimal]], day: dt.date) -> Decimal | None:
    """The close of `day` or the last one before it."""
    before = [close for d, close in closes if d <= day]
    return before[-1] if before else None


def _plain(close: Decimal) -> Decimal:
    """A stored close (8 places) as XTB writes it: at least 2 places, more only when they carry digits."""
    trimmed = close.normalize()
    return close.quantize(PRICE) if -trimmed.as_tuple().exponent <= 2 else trimmed


def _trim(value: Decimal) -> Decimal:
    """Without trailing zeros (500.50000000 → 500.5), never in exponent form (1E+1)."""
    trimmed = value.normalize()
    return trimmed.quantize(ONE) if trimmed.as_tuple().exponent > 0 else trimmed
