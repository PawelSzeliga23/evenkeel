"""A small portfolio with known numbers, shared by the valuation, portfolio and positions tests.

SXR8.DE (EUR): 500 EUR on 2026-03-02, 600 EUR on 2026-09-25; EUR: 4.30 PLN from 2026-02-20, 4.25 from 2026-09-25.
Account: deposit 10 000 zł (03-01), 2 × SXR8.DE for 4 304.30 zł (03-02, lot 777), dividend 40 zł − 6 zł tax (06-15).
On Saturday 2026-09-26: position 2 × 600 × 4.25 = 5 100.00 zł, cash 5 729.70 zł.
"""
import datetime as dt
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Account, FxRate, ImportRecord, Instrument, PositionLot, Price, Transaction, User, XtbSnapshot
from app.valuation.service import mark_stale, recompute_user

AT_DEPOSIT = dt.datetime(2026, 3, 1, 10, 0, tzinfo=dt.UTC)
AT_BUY = dt.datetime(2026, 3, 2, 9, 30, tzinfo=dt.UTC)
AT_DIVIDEND = dt.datetime(2026, 6, 15, 12, 0, tzinfo=dt.UTC)
THU, FRI, SAT = dt.date(2026, 9, 24), dt.date(2026, 9, 25), dt.date(2026, 9, 26)


def seed_market(db: Session) -> int:
    instrument = Instrument(
        xtb_ticker="SXR8.DE", name="Core S&P 500", category="etf", currency="EUR", price_symbol="SXR8.DE",
        price_checked_at=dt.datetime(2026, 9, 25, 21, 0, tzinfo=dt.UTC),
    )
    db.add(instrument)
    db.flush()
    db.add_all([
        Price(instrument_id=instrument.id, date=dt.date(2026, 3, 2), close=Decimal("500.00"), source="yahoo"),
        Price(instrument_id=instrument.id, date=FRI, close=Decimal("600.00"), source="yahoo"),
        FxRate(currency="EUR", date=dt.date(2026, 2, 20), rate_pln=Decimal("4.30")),
        FxRate(currency="EUR", date=FRI, rate_pln=Decimal("4.25")),
    ])
    db.commit()
    return instrument.id


def seed_user(db: Session, email: str = "anna@portfolio.dev") -> int:
    user = User(email=email, password_hash="x")
    db.add(user)
    db.commit()
    return user.id


def seed_holdings(db: Session, user_id: int, instrument_id: int, number: str = "56216965") -> int:
    account = Account(user_id=user_id, name="XTB IKE", kind="broker", wrapper="ike", broker="xtb",
                      external_account_number=number, currency="PLN")
    db.add(account)
    db.flush()

    def tx(external_id: str, type_: str, at: dt.datetime, amount: str, **fields: object) -> Transaction:
        return Transaction(account_id=account.id, type=type_, xtb_type=type_, occurred_at=at, amount=Decimal(amount),
                           currency="PLN", external_id=external_id, comment="", raw={}, **fields)

    db.add_all([
        tx("1", "deposit", AT_DEPOSIT, "10000"),
        tx("2", "buy", AT_BUY, "-4304.30", instrument_id=instrument_id, quantity=Decimal("2"),
           price=Decimal("500.5"), xtb_position_id="777"),
        tx("3", "dividend", AT_DIVIDEND, "40.00", instrument_id=instrument_id),
        tx("4", "withholding_tax", AT_DIVIDEND, "-6.00", instrument_id=instrument_id),
        PositionLot(account_id=account.id, instrument_id=instrument_id, xtb_position_id="777", side="buy",
                    quantity=Decimal("2"), open_price=Decimal("500.5"), opened_at=AT_BUY,
                    stop_loss=Decimal("450"), raw={}),
    ])
    db.commit()
    return account.id


def seed_snapshot(db: Session, account_id: int, instrument_id: int, volume: str) -> None:
    """An XTB import taken on Saturday 2026-09-26 reporting `volume` units worth 5 100 zł."""
    account = db.get(Account, account_id)
    record = ImportRecord(user_id=account.user_id, account_id=account_id, filename="IKE.xlsx", file_hash="0" * 64,
                          rows_added=0, rows_duplicate=0, rows_unknown=0)
    db.add(record)
    db.flush()
    db.add(XtbSnapshot(import_id=record.id, account_id=account_id, instrument_id=instrument_id,
                       row_kind="instrument_summary", volume=Decimal(volume), value=Decimal("5100"),
                       taken_at=dt.datetime(2026, 9, 26, 12, 0, tzinfo=dt.UTC), raw={}))
    db.commit()


def valuate(db: Session, user_id: int, today: dt.date = SAT) -> None:
    mark_stale(db, [user_id], dt.date.min)
    db.commit()
    recompute_user(db, user_id, today)
