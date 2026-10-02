"""Weekly closes of CD Projekt for the web e2e price chart: `python -m tests.e2e_prices` (inside api-e2e, after the
import created the instrument). The e2e API has no market provider, so without these the chart has no line.
Values are made up: 240 zł in December 2025 rising to 282 zł."""
import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.db import get_sessionmaker
from app.models import Instrument, Price

START = dt.date(2025, 12, 1)
WEEKS = 40


def main() -> None:
    with get_sessionmaker()() as db:
        instrument_id = db.scalar(select(Instrument.id).where(Instrument.xtb_ticker == "CDR.PL"))
        if instrument_id is None:
            raise SystemExit("CDR.PL nie istnieje — najpierw import.")
        known = set(db.scalars(select(Price.date).where(Price.instrument_id == instrument_id)))
        for week in range(WEEKS):
            day = START + dt.timedelta(weeks=week)
            if day not in known:
                db.add(Price(instrument_id=instrument_id, date=day, close=Decimal(240 + week) + Decimal("0.05"),
                             source="e2e"))
        db.commit()


if __name__ == "__main__":
    main()
