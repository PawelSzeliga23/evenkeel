import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.market.store import (
    delete_prices,
    fx_date_bounds,
    fx_on,
    last_price_date,
    latest_prices,
    price_on,
    replace_provider_splits,
    upsert_cpi,
    upsert_fx_rates,
    upsert_prices,
    upsert_ref_rates,
)
from app.market.types import CpiPoint, FxPoint, PriceBar, RefRatePoint, SplitEvent
from app.models import CorporateAction, Cpi, FxRate, Instrument, NbpRefRate, Price

FRI = dt.date(2026, 9, 4)
SUN = dt.date(2026, 9, 6)
MON = dt.date(2026, 9, 7)


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _instrument(db: Session, ticker: str = "SXR8.DE") -> Instrument:
    instrument = Instrument(xtb_ticker=ticker, name=ticker)
    db.add(instrument)
    db.commit()
    return instrument


def _count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_price_upsert_is_idempotent_and_updates_values(db: Session) -> None:
    instrument = _instrument(db)
    bars = [PriceBar(FRI, Decimal("711.72"), Decimal("700.5")), PriceBar(MON, Decimal("713.80"))]

    upsert_prices(db, instrument.id, bars, "yahoo")
    upsert_prices(db, instrument.id, [PriceBar(MON, Decimal("714.02"))], "yahoo")
    db.commit()

    assert _count(db, Price) == 2
    assert price_on(db, instrument.id, MON).close == Decimal("714.02")
    assert price_on(db, instrument.id, FRI).adj_close == Decimal("700.5")


def test_duplicate_keys_in_one_batch_keep_the_last(db: Session) -> None:
    instrument = _instrument(db)

    count = upsert_prices(db, instrument.id, [PriceBar(FRI, Decimal("1")), PriceBar(FRI, Decimal("2"))], "yahoo")
    db.commit()

    assert count == 1
    assert price_on(db, instrument.id, FRI).close == Decimal("2")


def test_large_history_is_written_in_chunks(db: Session) -> None:
    instrument = _instrument(db)
    bars = [PriceBar(dt.date(2010, 1, 1) + dt.timedelta(days=i), Decimal(i)) for i in range(2500)]

    assert upsert_prices(db, instrument.id, bars, "yahoo") == 2500
    db.commit()

    assert _count(db, Price) == 2500
    assert last_price_date(db, instrument.id) == dt.date(2010, 1, 1) + dt.timedelta(days=2499)


def test_empty_upsert_writes_nothing(db: Session) -> None:
    instrument = _instrument(db)

    assert upsert_prices(db, instrument.id, [], "yahoo") == 0
    assert last_price_date(db, instrument.id) is None


def test_price_on_uses_last_known_price(db: Session) -> None:
    instrument = _instrument(db)
    upsert_prices(db, instrument.id, [PriceBar(FRI, Decimal("711.72")), PriceBar(MON, Decimal("713.80"))], "yahoo")
    db.commit()

    assert price_on(db, instrument.id, SUN).date == FRI
    assert price_on(db, instrument.id, FRI - dt.timedelta(days=1)) is None


def test_fx_on_uses_last_known_rate_and_pln_is_one(db: Session) -> None:
    upsert_fx_rates(db, "EUR", [FxPoint(FRI, Decimal("4.3179")), FxPoint(MON, Decimal("4.3100"))])
    db.commit()

    assert fx_on(db, "EUR", SUN) == Decimal("4.3179")
    assert fx_on(db, "PLN", SUN) == Decimal(1)
    assert fx_on(db, "USD", SUN) is None
    assert fx_date_bounds(db, "EUR") == (FRI, MON)
    assert fx_date_bounds(db, "USD") == (None, None)


def test_latest_prices_returns_newest_row_per_instrument(db: Session) -> None:
    first, second = _instrument(db, "SXR8.DE"), _instrument(db, "VIE.FR")
    upsert_prices(db, first.id, [PriceBar(FRI, Decimal("1")), PriceBar(MON, Decimal("2"))], "yahoo")
    upsert_prices(db, second.id, [PriceBar(FRI, Decimal("30"))], "yahoo")
    db.commit()

    latest = latest_prices(db, [first.id, second.id])

    assert {key: (row.date, row.close) for key, row in latest.items()} == {
        first.id: (MON, Decimal("2")), second.id: (FRI, Decimal("30")),
    }
    assert latest_prices(db, []) == {}


def test_delete_prices_removes_only_that_instrument(db: Session) -> None:
    first, second = _instrument(db, "SXR8.DE"), _instrument(db, "VIE.FR")
    upsert_prices(db, first.id, [PriceBar(FRI, Decimal("1"))], "yahoo")
    upsert_prices(db, second.id, [PriceBar(FRI, Decimal("30"))], "yahoo")

    assert delete_prices(db, first.id) == 1
    db.commit()

    assert _count(db, Price) == 1


def test_cpi_and_ref_rate_upserts_are_idempotent(db: Session) -> None:
    cpi = [CpiPoint(dt.date(2026, 7, 1), Decimal("3.0")), CpiPoint(dt.date(2026, 8, 1), Decimal("3.4"))]
    refs = [RefRatePoint(dt.date(2026, 3, 5), Decimal("3.75"))]

    for _ in range(2):
        upsert_cpi(db, cpi)
        upsert_ref_rates(db, refs)
    upsert_cpi(db, [CpiPoint(dt.date(2026, 8, 1), Decimal("3.5"))])
    db.commit()

    assert (_count(db, Cpi), _count(db, NbpRefRate), _count(db, FxRate)) == (2, 1, 0)
    assert db.scalar(select(Cpi.yoy).where(Cpi.year_month == dt.date(2026, 8, 1))) == Decimal("3.5")


def _actions(db: Session, instrument_id: int) -> list[tuple]:
    rows = db.scalars(select(CorporateAction).where(CorporateAction.instrument_id == instrument_id)
                      .order_by(CorporateAction.effective_date, CorporateAction.source))
    return [(a.type, a.effective_date, a.ratio_from, a.ratio_to, a.source) for a in rows]


def test_provider_splits_are_replaced_only_inside_the_fetched_window(db: Session) -> None:
    instrument = _instrument(db, "NVDA.US")
    old = SplitEvent(dt.date(2021, 7, 20), Decimal(1), Decimal(4))
    new = SplitEvent(dt.date(2024, 6, 10), Decimal(1), Decimal(10))
    db.add(CorporateAction(instrument_id=instrument.id, type="split", effective_date=dt.date(2024, 6, 10),
                           ratio_from=Decimal(1), ratio_to=Decimal(10), source="xtb"))

    assert replace_provider_splits(db, instrument.id, [old, new], None) is True
    assert replace_provider_splits(db, instrument.id, [new], dt.date(2024, 1, 1)) is False
    assert replace_provider_splits(db, instrument.id, [], dt.date(2025, 1, 1)) is False
    db.commit()

    assert _actions(db, instrument.id) == [
        ("split", dt.date(2021, 7, 20), Decimal(1), Decimal(4), "provider"),
        ("split", dt.date(2024, 6, 10), Decimal(1), Decimal(10), "provider"),
        ("split", dt.date(2024, 6, 10), Decimal(1), Decimal(10), "xtb"),
    ]


def test_reverse_split_and_changed_ratio_are_detected(db: Session) -> None:
    instrument = _instrument(db, "XYZ.US")
    replace_provider_splits(db, instrument.id, [SplitEvent(dt.date(2025, 3, 3), Decimal(10), Decimal(1))], None)

    changed = replace_provider_splits(db, instrument.id, [SplitEvent(dt.date(2025, 3, 3), Decimal(20), Decimal(1))], None)
    db.commit()

    assert changed is True
    assert _actions(db, instrument.id) == [("reverse_split", dt.date(2025, 3, 3), Decimal(20), Decimal(1), "provider")]
