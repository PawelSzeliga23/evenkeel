import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Cpi, FxRate, Instrument, NbpRefRate, Price

DAY = dt.date(2026, 9, 25)


def _instrument(session: Session) -> Instrument:
    instrument = Instrument(xtb_ticker="SXR8.DE", name="Core S&P 500")
    session.add(instrument)
    session.flush()
    return instrument


def test_price_is_unique_per_instrument_and_day(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        instrument = _instrument(session)
        row = {"instrument_id": instrument.id, "date": DAY, "close": Decimal("713.8"), "source": "yahoo"}
        session.execute(insert(Price).values(row))
        with pytest.raises(IntegrityError):
            session.execute(insert(Price).values(row))


def test_deleting_instrument_deletes_its_prices(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        instrument = _instrument(session)
        session.add(Price(instrument_id=instrument.id, date=DAY, close=Decimal("713.8"), source="yahoo"))
        session.commit()
        session.delete(instrument)
        session.commit()
        assert session.scalar(select(func.count()).select_from(Price)) == 0


def test_market_values_are_stored_exactly(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        session.add_all([
            FxRate(currency="HUF", date=DAY, rate_pln=Decimal("0.012345")),
            Cpi(year_month=dt.date(2026, 8, 1), yoy=Decimal("-0.9")),
            NbpRefRate(valid_from=dt.date(2026, 3, 5), rate=Decimal("3.75")),
        ])
        session.commit()
        assert session.scalar(select(FxRate.rate_pln)) == Decimal("0.012345")
        assert session.scalar(select(Cpi.yoy)) == Decimal("-0.90")
        assert session.scalar(select(NbpRefRate.rate)) == Decimal("3.75")


def test_new_instrument_has_no_price_status(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        instrument = _instrument(session)
        session.commit()
        session.refresh(instrument)
        assert (instrument.price_checked_at, instrument.price_error) == (None, None)
