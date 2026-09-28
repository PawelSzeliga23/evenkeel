import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.market.store import delete_prices, fx_on, last_price_date, price_on, upsert_fx_rates, upsert_prices
from app.market.types import FxPoint, PriceBar, PriceHistory, ProviderError
from app.market.update import (
    FX_MARGIN_DAYS,
    MSG_FAILED,
    MSG_NOT_FOUND,
    MSG_UNMAPPED,
    backfill_new_instruments,
    fx_currencies,
    fx_ranges_to_fetch,
    run_market_update,
    update_all_prices,
    update_fx,
)
from app.models import (
    Account,
    CorporateAction,
    Cpi,
    FxRate,
    Instrument,
    NbpRefRate,
    PositionLot,
    Price,
    Transaction,
    User,
)
from tests.market_fakes import NVDA, SXR8, FakeFx, FakeInflation, FakePrices, fake_providers

NOW = dt.datetime(2026, 9, 25, 21, 0, tzinfo=dt.UTC)
TODAY = dt.date(2026, 9, 25)


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _reference(db: Session, instrument: Instrument) -> None:
    """Instruments are shared across users; the worker only touches ones actually held or traded.

    A `PositionLot` is used here (rather than a `Transaction`) because it does not carry an
    `occurred_at`, so it cannot distort the `fx_needed_from` (earliest transaction) tests below.
    """
    user = User(email=f"ref-{instrument.id}@portfolio.dev", password_hash="x")
    db.add(user)
    db.flush()
    account = Account(
        user_id=user.id, name="Ref", kind="broker", wrapper="ike", broker="xtb",
        external_account_number=str(instrument.id), currency="PLN",
    )
    db.add(account)
    db.flush()
    db.add(PositionLot(
        account_id=account.id, instrument_id=instrument.id, xtb_position_id=str(instrument.id),
        side="buy", quantity=Decimal("1"), open_price=Decimal("1"),
        opened_at=dt.datetime(2020, 1, 1, tzinfo=dt.UTC), raw={},
    ))
    db.commit()


def _instrument(db: Session, ticker: str, **fields: object) -> Instrument:
    instrument = Instrument(xtb_ticker=ticker, name=ticker, **fields)
    db.add(instrument)
    db.commit()
    _reference(db, instrument)
    return instrument


def _first_transaction_at(db: Session, occurred_at: dt.datetime) -> None:
    user = User(email="anna@portfolio.dev", password_hash="x")
    db.add(user)
    db.flush()
    account = Account(user_id=user.id, name="XTB IKE", kind="broker", wrapper="ike", broker="xtb",
                      external_account_number="56216965", currency="PLN")
    db.add(account)
    db.flush()
    db.add(Transaction(account_id=account.id, type="deposit", xtb_type="Deposit", occurred_at=occurred_at,
                       amount=Decimal("100"), currency="PLN", external_id="1", comment="", raw={}))
    db.commit()


def test_first_sight_fetches_full_history_and_fills_symbol_and_currency(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE")
    prices = FakePrices({"SXR8.DE": SXR8})

    rows, failed = update_all_prices(db, prices, NOW)

    assert (rows, failed, prices.calls) == (2, [], [("SXR8.DE", None)])
    db.refresh(instrument)
    assert (instrument.price_symbol, instrument.currency, instrument.price_error) == ("SXR8.DE", "EUR", None)
    assert instrument.price_checked_at == NOW
    assert price_on(db, instrument.id, TODAY).close == Decimal("713.80")


def test_known_instrument_is_updated_from_last_stored_day_with_overlap(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE", price_symbol="SXR8.DE", currency="EUR")
    upsert_prices(db, instrument.id, [PriceBar(dt.date(2026, 9, 10), Decimal("700"))], "fake")
    db.commit()
    prices = FakePrices({"SXR8.DE": SXR8})

    update_all_prices(db, prices, NOW)

    assert prices.calls == [("SXR8.DE", dt.date(2026, 9, 5))]
    assert last_price_date(db, instrument.id) == TODAY


def test_manual_symbol_is_used_and_never_overwritten(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE", price_symbol="SXR8.F", price_symbol_overridden=True)
    prices = FakePrices({"SXR8.F": SXR8})

    update_all_prices(db, prices, NOW)

    assert prices.calls == [("SXR8.F", None)]
    db.refresh(instrument)
    assert (instrument.price_symbol, instrument.price_symbol_overridden) == ("SXR8.F", True)


def test_unmapped_exchange_is_marked_without_calling_provider(db: Session) -> None:
    instrument = _instrument(db, "ASML.NL")
    prices = FakePrices()

    rows, failed = update_all_prices(db, prices, NOW)

    assert (rows, failed, prices.calls) == (0, ["ASML.NL"], [])
    db.refresh(instrument)
    assert (instrument.price_symbol, instrument.price_error) == (None, MSG_UNMAPPED)


def test_one_failing_instrument_does_not_stop_the_others(db: Session) -> None:
    failing = _instrument(db, "VIE.FR")
    working = _instrument(db, "SXR8.DE")
    missing = _instrument(db, "PKN.PL")
    prices = FakePrices({"SXR8.DE": SXR8}, errors={"VIE.PA": ProviderError("HTTP 503")})

    rows, failed = update_all_prices(db, prices, NOW)

    assert (rows, failed) == (2, ["VIE.FR", "PKN.PL"])
    for instrument in (failing, working, missing):
        db.refresh(instrument)
    assert failing.price_error == MSG_FAILED.format(symbol="VIE.PA")
    assert missing.price_error == MSG_NOT_FOUND.format(symbol="PKN.WA")
    assert (working.price_error, last_price_date(db, working.id)) == (None, TODAY)


def test_stale_instrument_is_refreshed_before_the_update(db: Session, engine: Engine) -> None:
    """A PATCH committed after the worker's instrument list was loaded must still be seen per instrument:
    the list is a plain Python list kept for the whole run, and the session identity map would otherwise
    keep serving the pre-PATCH copy (old symbol, old override flag) for it.
    """
    instrument = _instrument(db, "SXR8.DE", price_symbol="SXR8.DE", price_checked_at=NOW - dt.timedelta(days=1))
    upsert_prices(db, instrument.id, [PriceBar(dt.date(2026, 9, 20), Decimal("700"))], "yahoo")
    db.commit()

    with Session(engine, expire_on_commit=False) as other:
        other_instrument = other.get(Instrument, instrument.id)
        other_instrument.price_symbol = "SXR8.F"
        other_instrument.price_symbol_overridden = True
        other_instrument.price_checked_at = None
        delete_prices(other, instrument.id)
        other.commit()

    prices = FakePrices({"SXR8.F": SXR8})
    rows, failed = update_all_prices(db, prices, NOW)

    assert (rows, failed, prices.calls) == (2, [], [("SXR8.F", None)])
    db.refresh(instrument)
    assert (instrument.price_symbol, instrument.price_symbol_overridden, instrument.price_error) == ("SXR8.F", True, None)
    assert last_price_date(db, instrument.id) == TODAY


def test_unexpected_error_for_one_instrument_does_not_stop_the_run(db: Session) -> None:
    """Not just ProviderError: a malformed-but-valid provider response (or a DB error) must not stop the
    worker mid-run or make it skip FX/CPI/ref-rates for the rest of the day.
    """
    first = _instrument(db, "SXR8.DE")
    middle = _instrument(db, "VIE.FR")
    last = _instrument(db, "AAPL.US")
    prices = FakePrices(
        {"SXR8.DE": SXR8, "AAPL": SXR8},
        errors={"VIE.PA": ValueError("malformed json from the provider")},
    )

    rows, failed = update_all_prices(db, prices, NOW)

    assert (rows, failed) == (4, ["VIE.FR"])
    for instrument in (first, middle, last):
        db.refresh(instrument)
    assert (middle.price_error, middle.price_checked_at) == (MSG_FAILED.format(symbol="VIE.FR"), NOW)
    assert (first.price_error, last.price_error) == (None, None)
    assert last_price_date(db, first.id) == TODAY
    assert last_price_date(db, last.id) == TODAY


def test_success_clears_previous_error(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE", price_error="stary błąd")

    update_all_prices(db, FakePrices({"SXR8.DE": SXR8}), NOW)

    db.refresh(instrument)
    assert instrument.price_error is None


def test_backfill_only_touches_instruments_never_checked(db: Session) -> None:
    _instrument(db, "SXR8.DE")
    _instrument(db, "VIE.FR", price_checked_at=NOW - dt.timedelta(hours=1))
    prices = FakePrices({"SXR8.DE": SXR8})

    rows, failed = backfill_new_instruments(db, prices, NOW)

    assert (rows, failed, prices.calls) == (2, [], [("SXR8.DE", None)])
    assert backfill_new_instruments(db, prices, NOW) == (0, [])


def test_unreferenced_instrument_is_not_fetched(db: Session) -> None:
    """Instruments are shared; an import can create one that no user actually holds or traded yet."""
    unreferenced = Instrument(xtb_ticker="ORLEN.PL", name="ORLEN.PL")
    db.add(unreferenced)
    db.commit()
    prices = FakePrices()

    rows, failed = update_all_prices(db, prices, NOW)

    assert (rows, failed, prices.calls) == (0, [], [])
    db.refresh(unreferenced)
    assert unreferenced.price_checked_at is None


def test_unreferenced_instrument_is_not_backfilled(db: Session) -> None:
    unreferenced = Instrument(xtb_ticker="ORLEN.PL", name="ORLEN.PL")
    db.add(unreferenced)
    db.commit()
    prices = FakePrices()

    rows, failed = backfill_new_instruments(db, prices, NOW)

    assert (rows, failed, prices.calls) == (0, [], [])
    db.refresh(unreferenced)
    assert unreferenced.price_checked_at is None


def test_unreferenced_instrument_currency_is_excluded_from_fx(db: Session) -> None:
    _instrument(db, "SXR8.DE", currency="EUR")
    unreferenced = Instrument(xtb_ticker="ORLEN.PL", name="ORLEN.PL", currency="USD")
    db.add(unreferenced)
    db.commit()
    fx = FakeFx()

    update_fx(db, fx, TODAY)

    assert [currency for currency, _, _ in fx.calls] == ["EUR"]


@pytest.mark.parametrize(
    ("stored", "needed_from", "expected"),
    [
        ((None, None), dt.date(2026, 2, 20), [(dt.date(2026, 2, 20), TODAY)]),
        ((dt.date(2026, 3, 1), dt.date(2026, 9, 20)), dt.date(2026, 3, 5), [(dt.date(2026, 9, 21), TODAY)]),
        ((dt.date(2026, 3, 1), TODAY), dt.date(2025, 1, 1), [(dt.date(2025, 1, 1), dt.date(2026, 2, 28))]),
        ((dt.date(2026, 3, 1), dt.date(2026, 9, 20)), dt.date(2025, 1, 1),
         [(dt.date(2025, 1, 1), dt.date(2026, 2, 28)), (dt.date(2026, 9, 21), TODAY)]),
        ((dt.date(2026, 3, 1), TODAY), dt.date(2026, 3, 1), []),
    ],
    ids=["nothing-stored", "tail-only", "older-history-imported-later", "gap-and-tail", "up-to-date"],
)
def test_fx_ranges_to_fetch(
    stored: tuple[dt.date | None, dt.date | None], needed_from: dt.date, expected: list[tuple[dt.date, dt.date]]
) -> None:
    assert fx_ranges_to_fetch(stored[0], stored[1], needed_from, TODAY) == expected


def test_fx_is_fetched_for_foreign_quote_currencies_from_first_transaction(db: Session) -> None:
    _first_transaction_at(db, dt.datetime(2026, 3, 2, 9, 30, tzinfo=dt.UTC))
    for ticker, currency in (("SXR8.DE", "EUR"), ("VIE.FR", "EUR"), ("AAPL.US", "USD"), ("PKN.PL", "PLN"), ("X.NL", None)):
        _instrument(db, ticker, currency=currency)
    fx = FakeFx()

    rows, failed = update_fx(db, fx, TODAY)

    start = dt.date(2026, 3, 2) - dt.timedelta(days=FX_MARGIN_DAYS)
    assert fx.calls == [("EUR", start, TODAY), ("USD", start, TODAY)]
    assert (rows, failed) == (4, [])
    assert fx_on(db, "USD", TODAY) == Decimal("4.3000")


def test_fx_without_transactions_starts_shortly_before_today(db: Session) -> None:
    _instrument(db, "SXR8.DE", currency="EUR")
    fx = FakeFx()

    update_fx(db, fx, TODAY)

    assert fx.calls == [("EUR", TODAY - dt.timedelta(days=FX_MARGIN_DAYS), TODAY)]


def test_fx_gap_before_stored_history_is_filled(db: Session) -> None:
    _instrument(db, "SXR8.DE", currency="EUR")
    upsert_fx_rates(db, "EUR", [FxPoint(dt.date(2026, 3, 1), Decimal("4.2")), FxPoint(TODAY, Decimal("4.3"))])
    _first_transaction_at(db, dt.datetime(2025, 1, 15, tzinfo=dt.UTC))
    fx = FakeFx()

    update_fx(db, fx, TODAY)

    assert fx.calls == [("EUR", dt.date(2025, 1, 5), dt.date(2026, 2, 28))]


def test_fx_failure_is_reported_and_other_currencies_continue(db: Session) -> None:
    _instrument(db, "SXR8.DE", currency="EUR")

    rows, failed = update_fx(db, FakeFx(error=ProviderError("HTTP 503")), TODAY)

    assert (rows, failed) == (0, ["EUR"])
    assert db.scalar(select(func.count()).select_from(FxRate)) == 0


def test_run_market_update_fills_everything_and_isolates_source_errors(db: Session) -> None:
    _instrument(db, "SXR8.DE")
    providers = fake_providers(inflation=FakeInflation(error=ProviderError("GUS down")))

    summary = run_market_update(db, providers, NOW, TODAY)

    assert (summary.price_rows, summary.failed_instruments) == (2, [])
    assert summary.fx_rows == 2  # currency EUR came from the price provider in the same run
    assert (summary.cpi_rows, summary.ref_rate_rows, summary.failed_sources) == (0, 1, ["cpi"])
    assert db.scalar(select(func.count()).select_from(Cpi)) == 0
    assert db.scalar(select(NbpRefRate.rate)) == Decimal("3.75")


def test_fx_unexpected_error_is_isolated_like_a_provider_error(db: Session) -> None:
    _instrument(db, "SXR8.DE", currency="EUR")

    rows, failed = update_fx(db, FakeFx(error=ValueError("boom")), TODAY)

    assert (rows, failed) == (0, ["EUR"])
    assert db.scalar(select(func.count()).select_from(FxRate)) == 0


def test_run_market_update_isolates_unexpected_source_errors(db: Session) -> None:
    _instrument(db, "SXR8.DE")
    providers = fake_providers(inflation=FakeInflation(error=ValueError("GUS returned garbage")))

    summary = run_market_update(db, providers, NOW, TODAY)

    assert (summary.price_rows, summary.failed_instruments) == (2, [])
    assert summary.fx_rows == 2  # currency EUR came from the price provider in the same run
    assert (summary.cpi_rows, summary.ref_rate_rows, summary.failed_sources) == (0, 1, ["cpi"])
    assert db.scalar(select(func.count()).select_from(Cpi)) == 0
    assert db.scalar(select(NbpRefRate.rate)) == Decimal("3.75")


def test_price_update_reports_the_earliest_written_day(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE")
    changed: dict[int, dt.date] = {}

    update_all_prices(db, FakePrices({"SXR8.DE": SXR8}), NOW, changed)

    assert changed == {instrument.id: dt.date(2026, 9, 24)}


def test_new_provider_split_is_stored_and_marks_the_whole_history(db: Session) -> None:
    instrument = _instrument(db, "NVDA.US")
    provider = FakePrices({"NVDA": NVDA})
    first: dict[int, dt.date] = {}
    second: dict[int, dt.date] = {}

    update_all_prices(db, provider, NOW, first)
    update_all_prices(db, provider, NOW, second)

    action = db.scalar(select(CorporateAction).where(CorporateAction.instrument_id == instrument.id))
    assert (action.type, action.effective_date, action.ratio_from, action.ratio_to, action.source) == (
        "split", dt.date(2024, 6, 10), Decimal(1), Decimal(10), "provider")
    assert first == {instrument.id: dt.date.min}
    assert second == {instrument.id: dt.date(2024, 6, 7)}


def test_instrument_fetched_before_splits_existed_refetches_full_history_once(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE", splits_synced=False)
    upsert_prices(db, instrument.id, [PriceBar(dt.date(2026, 9, 1), Decimal("700"))], "yahoo")
    db.commit()
    provider = FakePrices({"SXR8.DE": SXR8})

    update_all_prices(db, provider, NOW)
    update_all_prices(db, provider, NOW)

    db.refresh(instrument)
    assert instrument.splits_synced is True
    assert provider.calls == [("SXR8.DE", None), ("SXR8.DE", dt.date(2026, 9, 20))]


def test_changed_currency_marks_the_whole_history(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE", currency="USD")
    upsert_prices(db, instrument.id, [PriceBar(dt.date(2026, 9, 23), Decimal("700"))], "yahoo")
    db.commit()
    changed: dict[int, dt.date] = {}

    update_all_prices(db, FakePrices({"SXR8.DE": SXR8}), NOW, changed)

    assert changed == {instrument.id: dt.date.min}


NVDA_FULL = PriceHistory(
    "NVDA", "USD",
    (PriceBar(dt.date(2024, 6, 3), Decimal("120.00")),) + NVDA.bars,
    splits=NVDA.splits,
)


def _nvda_on_the_old_basis(db: Session) -> Instrument:
    """NVDA stored before its 10:1 split was known: closes unadjusted, the last one on 2024-06-07."""
    instrument = _instrument(db, "NVDA.US", price_symbol="NVDA", currency="USD")
    upsert_prices(db, instrument.id, [
        PriceBar(dt.date(2024, 5, 31), Decimal("1100.00")),
        PriceBar(dt.date(2024, 6, 3), Decimal("1200.00")),
        PriceBar(dt.date(2024, 6, 7), Decimal("1208.90")),
    ], "yahoo")
    db.commit()
    return instrument


def _stored_closes(db: Session, instrument_id: int) -> dict[dt.date, Decimal]:
    return dict(db.execute(select(Price.date, Price.close).where(Price.instrument_id == instrument_id)).all())


def test_split_found_by_a_windowed_fetch_replaces_the_whole_stored_history(db: Session) -> None:
    instrument = _nvda_on_the_old_basis(db)
    provider = FakePrices({"NVDA": NVDA_FULL}, windowed={"NVDA": NVDA})
    changed: dict[int, dt.date] = {}

    update_all_prices(db, provider, NOW, changed)

    assert provider.calls == [("NVDA", dt.date(2024, 6, 2)), ("NVDA", None)]
    assert _stored_closes(db, instrument.id) == {bar.date: bar.close for bar in NVDA_FULL.bars}
    assert changed == {instrument.id: dt.date.min}
    assert db.scalar(select(func.count()).select_from(CorporateAction)
                     .where(CorporateAction.instrument_id == instrument.id)) == 1


def test_changed_currency_found_by_a_windowed_fetch_replaces_the_whole_stored_history(db: Session) -> None:
    instrument = _nvda_on_the_old_basis(db)
    in_eur = PriceHistory("NVDA", "EUR", (PriceBar(dt.date(2024, 6, 3), Decimal("110.00")),))
    provider = FakePrices({"NVDA": in_eur}, windowed={"NVDA": PriceHistory("NVDA", "EUR", ())})

    update_all_prices(db, provider, NOW)

    db.refresh(instrument)
    assert (instrument.currency, _stored_closes(db, instrument.id)) == ("EUR", {dt.date(2024, 6, 3): Decimal("110.00")})


def test_failed_full_refetch_is_reported_and_retried_in_full_next_time(db: Session) -> None:
    instrument = _nvda_on_the_old_basis(db)
    failing = FakePrices({"NVDA": NVDA_FULL}, windowed={"NVDA": NVDA}, full_errors={"NVDA": ProviderError("down")})

    rows, failed = update_all_prices(db, failing, NOW)

    db.refresh(instrument)
    assert (rows, failed, instrument.price_error) == (0, ["NVDA.US"], MSG_FAILED.format(symbol="NVDA"))
    assert instrument.splits_synced is False
    # Until the retry, the stored splits and closes stay on the same (old) basis: no split without adjusted closes.
    assert db.scalar(select(func.count()).select_from(CorporateAction)
                     .where(CorporateAction.instrument_id == instrument.id)) == 0
    assert _stored_closes(db, instrument.id)[dt.date(2024, 6, 3)] == Decimal("1200.00")
    provider = FakePrices({"NVDA": NVDA_FULL})
    update_all_prices(db, provider, NOW)
    assert provider.calls == [("NVDA", None)]
    assert _stored_closes(db, instrument.id)[dt.date(2024, 6, 3)] == Decimal("120.00")


def test_run_market_update_reports_changed_instruments(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE")
    summary = run_market_update(db, fake_providers(), NOW, TODAY)
    assert summary.prices_changed_from == {instrument.id: dt.date(2026, 9, 24)}


def test_fx_covers_currencies_of_foreign_currency_accounts(db: Session) -> None:
    user = User(email="usd@portfolio.dev", password_hash="x")
    db.add(user)
    db.flush()
    account = Account(user_id=user.id, name="XTB USD", kind="broker", wrapper="regular", broker="xtb",
                      external_account_number="99", currency="USD")
    db.add(account)
    db.flush()
    db.add(Transaction(account_id=account.id, type="deposit", xtb_type="Deposit",
                       occurred_at=dt.datetime(2026, 9, 1, tzinfo=dt.UTC), amount=Decimal("100"), currency="USD",
                       external_id="1", comment="", raw={}))
    _instrument(db, "SXR8.DE", currency="EUR")

    assert fx_currencies(db) == ["EUR", "USD"]


def test_fx_update_reports_the_earliest_fetched_day(db: Session) -> None:
    _instrument(db, "SXR8.DE", currency="EUR")
    _first_transaction_at(db, dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.UTC))
    changed: dict[str, dt.date] = {}

    update_fx(db, FakeFx(), TODAY, changed)

    assert changed == {"EUR": dt.date(2026, 9, 1) - dt.timedelta(days=FX_MARGIN_DAYS)}


def test_fx_without_new_rows_reports_nothing(db: Session) -> None:
    _instrument(db, "SXR8.DE", currency="EUR")
    upsert_fx_rates(db, "EUR", [FxPoint(TODAY - dt.timedelta(days=30), Decimal("4.3")), FxPoint(TODAY, Decimal("4.2"))])
    db.commit()
    changed: dict[str, dt.date] = {}

    update_fx(db, FakeFx(), TODAY, changed)

    assert changed == {}


def test_conversion_target_gets_prices_although_nobody_traded_it(db: Session) -> None:
    source = _instrument(db, "SXR8.DE")
    target = Instrument(xtb_ticker="CSPX.UK", name="CSPX.UK")
    db.add(target)
    db.flush()
    owner = db.scalar(select(User.id).where(User.email == f"ref-{source.id}@portfolio.dev"))
    db.add(CorporateAction(instrument_id=source.id, type="conversion", effective_date=dt.date(2026, 9, 1),
                           ratio_from=Decimal(1), ratio_to=Decimal(1), target_instrument_id=target.id,
                           source="manual", user_id=owner))
    db.commit()
    cspx = PriceHistory("CSPX.L", "USD", (PriceBar(dt.date(2026, 9, 24), Decimal("610.00")),))

    backfill_new_instruments(db, FakePrices({"SXR8.DE": SXR8, "CSPX.L": cspx}), NOW)

    assert _stored_closes(db, target.id) == {dt.date(2026, 9, 24): Decimal("610.00000000")}
