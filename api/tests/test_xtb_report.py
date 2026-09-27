from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.xtb.report import parse_report, to_decimal
from app.xtb.workbook import XtbFormatError
from tests import xtb_factory as xf

BOUGHT_AT = datetime(2026, 3, 2, 9, 30)


def _ike_report(**overrides: object) -> bytes:
    params: dict = {
        "cash": [
            xf.cash_row("IKE deposit", 5000.0, "1001", datetime(2026, 3, 1, 8, 0),
                        comment="Transfer in operation on account with id 56204082"),
            xf.buy_row("SXR8.DE", "2", "500.5", -4304.3, "1002", BOUGHT_AT, "777"),
            xf.cash_row("Mystery", 0.1, "1003", datetime(2026, 3, 3, 8, 0)),
        ],
        "open_rows": [
            xf.summary_row("SXR8.DE", "Core S&P 500", 2.0, 1020.0, 500.5, 19.0),
            xf.lot_row("SXR8.DE", "777", 2.0, 500.5, BOUGHT_AT, 510.0, 1020.0, 19.0),
        ],
        "open_positions_account_number": "56204082",  # XTB quirk: the regular account's number
    }
    params.update(overrides)
    return xf.build_report(**params)


def test_ike_report_identifies_account_period_and_wrapper() -> None:
    report = parse_report(xf.filename("IKE", "56216965"), _ike_report())

    assert report.account_number == "56216965"
    assert (report.wrapper, report.currency) == ("ike", "PLN")
    assert report.report_from == datetime(2006, 1, 1, tzinfo=UTC)
    assert report.report_to == datetime(2026, 9, 26, tzinfo=UTC)
    assert report.generated_at == datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
    assert report.has_open_positions is True
    assert len(report.file_hash) == 64


def test_cash_operations_are_parsed_exactly() -> None:
    operations = parse_report(xf.filename(), _ike_report()).cash_operations

    transfer, buy, mystery = operations
    assert (transfer.classified.type, transfer.classified.counterparty_account) == ("transfer_in", "56204082")
    assert buy.classified.type == "buy"
    assert (buy.classified.quantity, buy.classified.price) == (Decimal("2"), Decimal("500.5"))
    assert buy.amount == Decimal("-4304.3")
    assert buy.occurred_at == datetime(2026, 3, 2, 9, 30, tzinfo=UTC)
    assert (buy.ticker, buy.xtb_position_id, buy.external_id) == ("SXR8.DE", "777", "1002")
    assert mystery.classified.type == "unknown"
    assert mystery.amount == Decimal("0.1")
    assert buy.raw["Comment"] == "OPEN BUY 2 @ 500.5"
    assert buy.raw["Time"] == "2026-03-02T09:30:00"


def test_open_positions_split_into_summaries_lots_and_account_summary() -> None:
    report = parse_report(xf.filename(), _ike_report())

    (summary,) = report.instrument_summaries
    assert (summary.ticker, summary.name, summary.category, summary.volume) == ("SXR8.DE", "Core S&P 500", "ETF", Decimal("2.0"))
    (lot,) = report.open_lots
    assert (lot.xtb_position_id, lot.side, lot.quantity, lot.open_price) == ("777", "BUY", Decimal("2.0"), Decimal("500.5"))
    assert lot.opened_at == datetime(2026, 3, 2, 9, 30, tzinfo=UTC)
    assert [(row.metric, row.amount) for row in report.account_summary] == [
        ("Open position value", Decimal("1000.0")),
        ("Open position profit", Decimal("25.0")),
    ]


def test_closed_positions_are_parsed() -> None:
    closed = [xf.closed_row("VIE.FR", "555", 3.0, 28.5, datetime(2026, 1, 5, 10, 0), 30.1, datetime(2026, 2, 5, 10, 0))]

    (lot,) = parse_report(xf.filename(), _ike_report(closed=closed)).closed_lots

    assert (lot.xtb_position_id, lot.ticker, lot.quantity, lot.close_price) == ("555", "VIE.FR", Decimal("3.0"), Decimal("30.1"))
    assert lot.closed_at == datetime(2026, 2, 5, 10, 0, tzinfo=UTC)
    assert (lot.open_conversion_rate, lot.close_origin) == (Decimal("4.3"), "Client")


def test_regular_account_currency_comes_from_prefix() -> None:
    content = xf.build_report(account_number="56204082", product="My Trades", include_open=False)

    report = parse_report(xf.filename("PLN", "56204082"), content)

    assert (report.account_number, report.wrapper, report.currency) == ("56204082", "regular", "PLN")
    assert report.has_open_positions is False


def test_renamed_file_falls_back_to_metadata_and_product_column() -> None:
    content = _ike_report()

    report = parse_report("moj eksport.xlsx", content)

    assert (report.account_number, report.wrapper) == ("56216965", "ike")


def test_renamed_regular_account_currency_falls_back_to_account_summary() -> None:
    content = xf.build_report(
        account_number="56204082", product="My Trades", summary_currency="EUR",
        open_rows=[xf.summary_row("SXR8.DE", "Core S&P 500", 2.0, 1020.0, 500.5, 19.0)],
    )

    report = parse_report("eksport.xlsx", content)

    assert report.currency == "EUR"


def test_report_without_cash_operations_is_rejected() -> None:
    with pytest.raises(XtbFormatError) as exc_info:
        parse_report(xf.filename(), xf.build_report(include_cash=False))

    assert exc_info.value.code == "not_xtb_report"


def test_operation_without_id_is_rejected() -> None:
    content = xf.build_report(cash=[xf.cash_row("Deposit", 1.0, "", datetime(2026, 3, 1))])

    with pytest.raises(XtbFormatError) as exc_info:
        parse_report(xf.filename(), content)

    assert exc_info.value.code == "missing_value"


def test_closed_position_without_type_is_rejected() -> None:
    row = xf.closed_row("VIE.FR", "555", 3.0, 28.5, datetime(2026, 1, 5, 10, 0), 30.1, datetime(2026, 2, 5, 10, 0))
    closed = [{**row, "Type": ""}]

    with pytest.raises(XtbFormatError) as exc_info:
        parse_report(xf.filename(), _ike_report(closed=closed))

    assert exc_info.value.code == "missing_value"


def test_overlong_filename_is_truncated_for_display_only() -> None:
    long_name = "A" * 300 + ".xlsx"
    content = xf.build_report(cash=[xf.cash_row("Deposit", 1.0, "1", datetime(2026, 3, 1))])

    report = parse_report(long_name, content)

    assert len(report.filename) == 255
    assert report.filename == long_name[:255]


def test_to_decimal_rejects_nan_and_infinity() -> None:
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(XtbFormatError) as exc_info:
            to_decimal(bad, "Amount")
        assert exc_info.value.code == "bad_number"


def test_overlong_ticker_is_rejected() -> None:
    content = xf.build_report(cash=[xf.buy_row("X" * 41, "1", "10", -10.0, "1", datetime(2026, 3, 1), "1")])

    with pytest.raises(XtbFormatError) as exc_info:
        parse_report(xf.filename(), content)

    assert exc_info.value.code == "bad_value"
