"""Every entry of one user's history — imported and manual operations, bond purchases and payouts, savings
deposits, withdrawals and credited interest — in one list, newest first."""
import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.bonds import edo
from app.history.schemas import DeleteTarget, HistoryItem
from app.models import SavingsFlow
from app.savings.router import account_days
from app.savings.summary import capitalizations
from app.scoping import UserScope
from app.transactions.router import MANUAL
from app.valuation.engine import money
from app.valuation.fixed_income import payout_day, payout_per_bond
from app.valuation.service import load_fixed_income, local_day

SAVINGS_FLOW_TYPES = {True: "savings_deposit", False: "savings_withdrawal"}


def _pln(amount: Decimal, currency: str) -> Decimal | None:
    return amount if currency == "PLN" else None


def history_items(scope: UserScope, today: dt.date) -> list[HistoryItem]:
    db = scope.db
    accounts = {account.id: account for account in db.scalars(scope.accounts())}
    items: list[HistoryItem] = []

    for tx in db.scalars(scope.transactions()).unique():
        account = accounts[tx.account_id]
        items.append(HistoryItem(
            id=f"tx:{tx.id}", kind="transaction", type=tx.type, date=local_day(tx.occurred_at),
            account_id=account.id, account_name=account.name, instrument_id=tx.instrument_id, ticker=tx.ticker,
            name=tx.instrument.name if tx.instrument else None, quantity=tx.quantity, price=tx.price,
            price_currency=tx.instrument.currency if tx.instrument else None,
            amount=tx.amount, currency=tx.currency, amount_pln=_pln(tx.amount, tx.currency), note=tx.comment,
            delete=DeleteTarget(target="transaction", id=tx.id) if tx.xtb_type == MANUAL else None,
        ))

    fixed = load_fixed_income(scope)
    holdings = {holding.id: holding for holding in fixed.holdings}
    for bond in db.scalars(scope.bond_holdings()):
        account = accounts[bond.account_id]
        cost = money(Decimal(bond.quantity) * edo.NOMINAL)
        common = {"account_id": account.id, "account_name": account.name, "name": bond.series,
                  "quantity": Decimal(bond.quantity), "currency": "PLN", "note": bond.note}
        items.append(HistoryItem(id=f"bond:{bond.id}:purchase", kind="bond_purchase", type="bond_purchase",
                                 date=bond.purchase_date, amount=-cost, amount_pln=-cost,
                                 delete=DeleteTarget(target="bond", id=bond.id), **common))
        holding = holdings[bond.id]
        schedule = edo.periods(holding.purchase_date, holding.series, fixed.cpi)
        paid_on = payout_day(holding, schedule)
        if paid_on <= today:
            payout = money(Decimal(holding.quantity) * payout_per_bond(holding, schedule))
            items.append(HistoryItem(id=f"bond:{bond.id}:payout", kind="bond_payout", type="bond_payout",
                                     date=paid_on, amount=payout, amount_pln=payout, **common))

    for settings in db.scalars(scope.savings_accounts()):
        account = accounts[settings.account_id]
        common = {"account_id": account.id, "account_name": account.name, "currency": "PLN"}
        for flow in db.scalars(select(SavingsFlow).where(SavingsFlow.savings_account_id == settings.id)):
            items.append(HistoryItem(id=f"sflow:{flow.id}", kind="savings_flow",
                                     type=SAVINGS_FLOW_TYPES[flow.amount > 0], date=flow.date, amount=flow.amount,
                                     amount_pln=flow.amount, note=flow.note,
                                     delete=DeleteTarget(target="savings_flow", id=flow.id), **common))
        for cap in capitalizations(account_days(db, settings, account, today)):
            items.append(HistoryItem(id=f"scap:{settings.id}:{cap.period_end:%Y-%m}", kind="savings_interest",
                                     type="savings_interest", date=cap.credited_on, amount=cap.net,
                                     amount_pln=cap.net, tax=cap.tax, **common))

    items.sort(key=lambda item: (item.date, item.id), reverse=True)
    return items


def matches(item: HistoryItem, query: str) -> bool:
    text = " ".join(filter(None, [item.name, item.ticker, item.account_name, item.note])).casefold()
    return query.casefold() in text
