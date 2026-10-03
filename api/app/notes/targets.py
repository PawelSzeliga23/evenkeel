"""The holdings notes can be about (plan 7f-2): label, closed or open, and where the details are. Needs a replay of
the portfolio, so only the journal endpoints use it."""
import datetime as dt

from app.models import Account, BondHolding, Instrument, JournalEntry, Transaction
from app.notes.keys import columns, key_of
from app.notes.schemas import JournalEntryOut, TargetLinkOut, TargetOut
from app.portfolio.service import list_positions
from app.scoping import UserScope

BONDS = "obligacje skarbowe"
SAVINGS = "konto oszczędnościowe"


class Targets:
    def __init__(self, scope: UserScope, today: dt.date) -> None:
        self._scope = scope
        db = scope.db
        positions = list_positions(scope, None, today)
        open_keys = {f"i:{p.instrument_id}" for p in positions if p.kind == "instrument"}
        open_keys |= {f"b:{p.name}" for p in positions if p.kind == "bond"}  # a bond row's name is its series
        last_account: dict[int, int] = {}
        newest_first = scope.transactions().where(Transaction.instrument_id.is_not(None)).with_only_columns(
            Transaction.instrument_id, Transaction.account_id)
        for instrument_id, account_id in db.execute(newest_first):
            last_account.setdefault(instrument_id, account_id)
        self._items: dict[str, TargetOut] = {}
        for instrument in db.scalars(scope.instruments()):
            key = f"i:{instrument.id}"
            account_id = last_account.get(instrument.id)
            link = None if account_id is None else TargetLinkOut(kind="position", account_id=account_id,
                                                                 instrument_id=instrument.id)
            self._items[key] = TargetOut(key=key, label=instrument.xtb_ticker, sublabel=instrument.name,
                                         closed=key not in open_keys, link=link)
        newest_bond: dict[str, int] = {}
        for holding_id, series in db.execute(scope.bond_holdings().with_only_columns(BondHolding.id, BondHolding.series)):
            newest_bond[series] = holding_id  # ordered by purchase date: the last one is the newest
        for series, holding_id in newest_bond.items():
            key = f"b:{series}"
            self._items[key] = TargetOut(key=key, label=series, sublabel=BONDS, closed=key not in open_keys,
                                         link=TargetLinkOut(kind="bond", bond_holding_id=holding_id))
        for settings in db.scalars(scope.savings_accounts()):
            account = db.get(Account, settings.account_id)
            key = f"s:{settings.account_id}"
            self._items[key] = TargetOut(key=key, label=account.name if account else SAVINGS, sublabel=SAVINGS,
                                         closed=False, link=TargetLinkOut(kind="savings", account_id=settings.account_id))

    def get(self, key: str) -> TargetOut:
        known = self._items.get(key)
        if known is not None:
            return known
        # Notes outlive the holding: a series without the user's bonds, or an instrument no longer traded.
        cols = columns(key)
        if cols["instrument_id"] is not None:
            instrument = self._scope.db.get(Instrument, cols["instrument_id"])
            return TargetOut(key=key, label=instrument.xtb_ticker if instrument else key,
                             sublabel=instrument.name if instrument else None, closed=True, link=None)
        series = cols["bond_series"]
        return TargetOut(key=key, label=str(series) if series else SAVINGS, sublabel=BONDS if series else None,
                         closed=True, link=None)

    def choices(self) -> list[TargetOut]:
        """What an entry can be about: open holdings first, then closed ones, each alphabetically."""
        return sorted(self._items.values(), key=lambda t: (t.closed, t.label.casefold()))


def entry_out(entry: JournalEntry, targets: Targets) -> JournalEntryOut:
    key = key_of(entry.instrument_id, entry.bond_series, entry.account_id)
    return JournalEntryOut(id=entry.id, entry_date=entry.entry_date, body=entry.body, created_at=entry.created_at,
                           updated_at=entry.updated_at, target=None if key is None else targets.get(key))
