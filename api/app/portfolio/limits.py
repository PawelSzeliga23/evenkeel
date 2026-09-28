"""IKE / IKZE contributions per calendar year against the statutory limit. The limit is per person, so all of
the user's accounts of one wrapper count together; withdrawals do not give the limit back (spec §6)."""
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select

from app.models import Transaction, WrapperLimit
from app.portfolio.schemas import LimitAccountOut, LimitOut
from app.portfolio.service import amount_pln
from app.scoping import UserScope
from app.valuation.engine import ZERO, money
from app.valuation.service import local_day

LIMITED_WRAPPERS = ("ike", "ikze")
CONTRIBUTION_TYPES = ("deposit", "transfer_in")  # a transfer from the user's own regular account is a contribution


def wrapper_limits(scope: UserScope, today: dt.date) -> list[LimitOut]:
    db = scope.db
    accounts = [account for account in db.scalars(scope.accounts()) if account.wrapper in LIMITED_WRAPPERS]
    if not accounts:
        return []
    wrapper_of = {account.id: account.wrapper for account in accounts}
    transactions = list(db.scalars(scope.transactions().where(
        Transaction.account_id.in_(list(wrapper_of)), Transaction.type.in_(CONTRIBUTION_TYPES)
    )).unique())
    pair_ids = [t.transfer_pair_id for t in transactions if t.transfer_pair_id is not None]
    pairs = {row.id: row for row in db.execute(
        select(Transaction.id, Transaction.account_id, Transaction.type).where(Transaction.id.in_(pair_ids))
    )} if pair_ids else {}
    paid: dict[tuple[str, int], dict[int, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for transaction in transactions:
        pair = pairs.get(transaction.transfer_pair_id) if transaction.transfer_pair_id is not None else None
        if pair is not None and pair.type == "transfer_out" and wrapper_of.get(pair.account_id) == wrapper_of[transaction.account_id]:
            continue  # already counted when first deposited into the other IKE/IKZE account of the same wrapper
        year = local_day(transaction.occurred_at).year
        paid[(wrapper_of[transaction.account_id], year)][transaction.account_id] += amount_pln(db, transaction)
    limits = {(row.wrapper, row.year): row.limit_pln for row in db.scalars(select(WrapperLimit))}
    result = []
    for wrapper in sorted(set(wrapper_of.values())):
        first_year = min((year for kind, year in paid if kind == wrapper), default=today.year)
        for year in range(today.year, first_year - 1, -1):
            by_account = paid.get((wrapper, year), {})
            total = money(sum(by_account.values(), ZERO))
            limit = limits.get((wrapper, year))
            result.append(LimitOut(
                wrapper=wrapper, year=year, paid_pln=total,
                limit_pln=money(limit) if limit is not None else None,
                remaining_pln=money(max(limit - total, ZERO)) if limit is not None else None,
                exceeded=limit is not None and total > limit,
                accounts=[LimitAccountOut(account_id=account.id, name=account.name,
                                          paid_pln=money(by_account.get(account.id, ZERO)))
                          for account in accounts if account.wrapper == wrapper],
            ))
    return result
