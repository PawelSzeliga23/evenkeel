"""Closed investments: every sale with its realized gain, per instrument and account (with its dividends and
fees; a partly sold holding counts all of them), and in total. Computed live by replaying the history."""
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from app.portfolio.schemas import ClosedInvestmentOut, ClosedOut, ClosedSaleOut, ClosedTotalsOut
from app.portfolio.service import percent
from app.scoping import UserScope
from app.valuation.engine import ZERO, Key, Sale, money, replay
from app.valuation.service import load_inputs


def _totals(sold_cost: Decimal, realized: Decimal, dividends: Decimal, fees: Decimal) -> dict[str, Decimal | None]:
    total = realized + dividends + fees
    return {"sold_cost_pln": sold_cost, "realized_pln": realized, "dividends_net_pln": dividends, "fees_pln": fees,
            "total_pln": total, "return_pct": percent(total, sold_cost)}


def closed_investments(scope: UserScope, account_id: int | None, day: dt.date) -> ClosedOut:
    inputs = load_inputs(scope)
    book = replay(inputs.entries, inputs.splits, inputs.market, day, conversions=inputs.conversions)
    accounts = {account.id: account for account in scope.db.scalars(scope.accounts())}
    instruments = {instrument.id: instrument for instrument in scope.db.scalars(scope.instruments())}
    grouped: dict[Key, list[Sale]] = defaultdict(list)
    for sale in book.sales:
        if account_id is None or sale.account_id == account_id:
            grouped[(sale.account_id, sale.instrument_id)].append(sale)

    def names(key: Key) -> dict:
        instrument = instruments[key[1]]
        return {"account_id": key[0], "account_name": accounts[key[0]].name, "instrument_id": key[1],
                "ticker": instrument.xtb_ticker, "name": instrument.name}

    sales = [
        ClosedSaleOut(
            **names((s.account_id, s.instrument_id)), opened_on=s.opened_on, closed_on=s.day,
            holding_days=(s.day - s.opened_on).days, quantity=s.quantity, cost_pln=money(s.cost_pln),
            proceeds_pln=money(s.proceeds_pln), realized_pln=money(s.realized_pln),
            price_effect_pln=s.price_effect_pln, fx_effect_pln=money(s.fx_effect_pln),
            return_pct=percent(s.realized_pln, s.cost_pln), matched=s.matched,
        )
        for group in grouped.values() for s in group
    ]
    sales.sort(key=lambda s: (s.closed_on, s.ticker, s.account_id), reverse=True)
    investments = []
    for key, group in grouped.items():
        numbers = _totals(
            sum((money(s.cost_pln) for s in group), ZERO), sum((money(s.realized_pln) for s in group), ZERO),
            money(book.dividends.get(key, ZERO) + book.withholding.get(key, ZERO)), money(book.fees.get(key, ZERO)),
        )
        investments.append(ClosedInvestmentOut(
            **names(key), **numbers, status="partial" if book.lots.get(key) else "closed",
            first_buy=min(s.opened_on for s in group), last_sale=max(s.day for s in group),
        ))
    investments.sort(key=lambda i: (i.last_sale, i.ticker, i.account_id), reverse=True)

    def summed(field: str) -> Decimal:
        return sum((getattr(item, field) for item in investments), money(ZERO))

    totals = ClosedTotalsOut(**_totals(summed("sold_cost_pln"), summed("realized_pln"), summed("dividends_net_pln"),
                                       summed("fees_pln")))
    return ClosedOut(sales=sales, investments=investments, totals=totals)
