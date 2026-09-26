import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import PurePath
from typing import Any

from app.xtb.classify import Classified, classify
from app.xtb.workbook import XtbFormatError, open_workbook, read_sheet

CASH_SHEET = "Cash Operations"
OPEN_SHEET = "Open Positions"
CLOSED_SHEET = "Closed Positions"
REQUIRED_COLUMNS = {
    CASH_SHEET: frozenset({"Type", "Time", "Amount", "ID", "Comment"}),
    OPEN_SHEET: frozenset({"Instrument/Position", "Ticker", "Type", "Volume", "Open price"}),
    CLOSED_SHEET: frozenset({"Ticker", "Volume", "Close Price", "Position ID"}),
}
ACCOUNT_SUMMARY_HEADER = ("Product", "Metric", "Amount", "Currency")
_FILENAME = re.compile(r"^(?P<prefix>[A-Za-z]+)_(?P<number>\d+)_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}\.xlsx$")
_WRAPPERS = {"IKE": "ike", "IKZE": "ikze"}

Raw = dict[str, str | None]


@dataclass(frozen=True)
class CashOperation:
    external_id: str
    xtb_type: str
    classified: Classified
    occurred_at: datetime
    amount: Decimal
    instrument_name: str | None
    ticker: str | None
    category: str | None
    comment: str
    xtb_position_id: str | None
    product: str | None
    raw: Raw


@dataclass(frozen=True)
class InstrumentSummary:
    ticker: str
    name: str
    category: str | None
    volume: Decimal | None
    value: Decimal | None
    open_price: Decimal | None
    net_profit: Decimal | None
    net_profit_pct: Decimal | None
    gross_profit: Decimal | None
    raw: Raw


@dataclass(frozen=True)
class OpenLot:
    xtb_position_id: str
    ticker: str
    side: str
    quantity: Decimal
    open_price: Decimal
    opened_at: datetime
    current_price: Decimal | None
    value: Decimal | None
    net_profit: Decimal | None
    net_profit_pct: Decimal | None
    gross_profit: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    margin: Decimal | None
    open_commission: Decimal | None
    swap: Decimal | None
    rollover: Decimal | None
    raw: Raw


@dataclass(frozen=True)
class ClosedLot:
    xtb_position_id: str
    ticker: str
    name: str | None
    category: str | None
    side: str
    quantity: Decimal
    open_price: Decimal
    opened_at: datetime
    close_price: Decimal | None
    closed_at: datetime | None
    close_origin: str | None
    commission: Decimal | None
    swap: Decimal | None
    rollover: Decimal | None
    margin: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    open_conversion_rate: Decimal | None
    close_conversion_rate: Decimal | None
    raw: Raw


@dataclass(frozen=True)
class AccountSummaryRow:
    product: str | None
    metric: str
    amount: Decimal | None
    currency: str | None
    raw: Raw


@dataclass(frozen=True)
class XtbReport:
    filename: str
    file_hash: str
    account_number: str
    wrapper: str
    currency: str
    report_from: datetime | None
    report_to: datetime | None
    generated_at: datetime | None
    has_open_positions: bool
    cash_operations: tuple[CashOperation, ...]
    instrument_summaries: tuple[InstrumentSummary, ...]
    open_lots: tuple[OpenLot, ...]
    closed_lots: tuple[ClosedLot, ...]
    account_summary: tuple[AccountSummaryRow, ...]


def to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def to_decimal(value: Any, field: str) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise XtbFormatError("bad_number", f"Nieprawidłowa liczba w kolumnie „{field}”: {value}.")
    try:
        # str() of a float gives its shortest round-trip form, so 0.1 becomes Decimal("0.1").
        return Decimal(str(value).replace(",", ".").replace(" ", ""))
    except InvalidOperation as exc:
        raise XtbFormatError("bad_number", f"Nieprawidłowa liczba w kolumnie „{field}”: {value}.") from exc


def to_utc(value: Any, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        try:
            value = datetime.fromisoformat(str(value))
        except ValueError as exc:
            raise XtbFormatError("bad_date", f"Nieprawidłowa data w kolumnie „{field}”: {value}.") from exc
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def jsonable(row: dict[str, Any]) -> Raw:
    return {key: value.isoformat() if isinstance(value, datetime) else to_text(value) for key, value in row.items()}


def _required(value: Any, what: str) -> Any:
    if value is None:
        raise XtbFormatError("missing_value", f"Brak wymaganej wartości: {what}.")
    return value


def parse_report(filename: str, content: bytes) -> XtbReport:
    name = PurePath(filename).name
    sheets = open_workbook(content)
    if CASH_SHEET not in sheets:
        raise XtbFormatError(
            "not_xtb_report",
            f"Plik {name} nie wygląda na eksport historii konta z XTB (brak zakładki „{CASH_SHEET}”).",
        )
    cash = read_sheet(CASH_SHEET, sheets[CASH_SHEET], REQUIRED_COLUMNS[CASH_SHEET])
    operations = tuple(_cash_operation(row) for row in cash.rows)

    match = _FILENAME.match(name)
    number = to_text(cash.metadata.get("Account number")) or (match["number"] if match else None)
    if not number:
        raise XtbFormatError("unknown_account", f"Nie udało się ustalić numeru rachunku XTB w pliku {name}.")
    prefix = match["prefix"].upper() if match else None
    products = {op.product.upper() for op in operations if op.product}
    wrapper = _WRAPPERS.get(prefix or "") or next((_WRAPPERS[p] for p in products if p in _WRAPPERS), "regular")
    currency = prefix if prefix and prefix not in _WRAPPERS and len(prefix) == 3 else "PLN"

    summaries: list[InstrumentSummary] = []
    lots: list[OpenLot] = []
    account_summary: tuple[AccountSummaryRow, ...] = ()
    generated_at = None
    if OPEN_SHEET in sheets:
        open_sheet = read_sheet(OPEN_SHEET, sheets[OPEN_SHEET], REQUIRED_COLUMNS[OPEN_SHEET])
        generated_at = to_utc(open_sheet.metadata.get("Data as of report generated"), "Data as of report generated")
        account_summary = _account_summary(open_sheet.pre_rows)
        for row in open_sheet.rows:
            ticker = to_text(row.get("Ticker"))
            if ticker is None:
                continue
            if to_text(row.get("Type")) is None:
                summaries.append(_summary(ticker, row))
            else:
                lots.append(_open_lot(ticker, row))

    closed: tuple[ClosedLot, ...] = ()
    if CLOSED_SHEET in sheets:
        closed_sheet = read_sheet(CLOSED_SHEET, sheets[CLOSED_SHEET], REQUIRED_COLUMNS[CLOSED_SHEET])
        closed = tuple(_closed_lot(row) for row in closed_sheet.rows if to_text(row.get("Ticker")))

    return XtbReport(
        filename=name,
        file_hash=hashlib.sha256(content).hexdigest(),
        account_number=number,
        wrapper=wrapper,
        currency=currency,
        report_from=to_utc(cash.metadata.get("Date from (UTC)"), "Date from (UTC)"),
        report_to=to_utc(cash.metadata.get("Date to (UTC)"), "Date to (UTC)"),
        generated_at=generated_at,
        has_open_positions=OPEN_SHEET in sheets,
        cash_operations=operations,
        instrument_summaries=tuple(summaries),
        open_lots=tuple(lots),
        closed_lots=closed,
        account_summary=account_summary,
    )


def _cash_operation(row: dict[str, Any]) -> CashOperation:
    external_id = _required(to_text(row.get("ID")), "ID operacji")
    occurred_at = _required(to_utc(row.get("Time"), "Time"), "czas operacji")
    amount = _required(to_decimal(row.get("Amount"), "Amount"), "kwota operacji")
    xtb_type = to_text(row.get("Type")) or ""
    comment = to_text(row.get("Comment")) or ""
    return CashOperation(
        external_id=external_id,
        xtb_type=xtb_type,
        classified=classify(xtb_type, comment),
        occurred_at=occurred_at,
        amount=amount,
        instrument_name=to_text(row.get("Instrument")),
        ticker=to_text(row.get("Ticker")),
        category=to_text(row.get("Category")),
        comment=comment,
        xtb_position_id=to_text(row.get("Position ID")),
        product=to_text(row.get("Product")),
        raw=jsonable(row),
    )


def _summary(ticker: str, row: dict[str, Any]) -> InstrumentSummary:
    return InstrumentSummary(
        ticker=ticker,
        name=to_text(row.get("Instrument/Position")) or ticker,
        category=to_text(row.get("Category")),
        volume=to_decimal(row.get("Volume"), "Volume"),
        value=to_decimal(row.get("Value"), "Value"),
        open_price=to_decimal(row.get("Open price"), "Open price"),
        net_profit=to_decimal(row.get("Net Profit"), "Net Profit"),
        net_profit_pct=to_decimal(row.get("Net Profit %"), "Net Profit %"),
        gross_profit=to_decimal(row.get("Gross Profit"), "Gross Profit"),
        raw=jsonable(row),
    )


def _open_lot(ticker: str, row: dict[str, Any]) -> OpenLot:
    return OpenLot(
        xtb_position_id=_required(to_text(row.get("Instrument/Position")), "numer pozycji"),
        ticker=ticker,
        side=to_text(row.get("Type")) or "BUY",
        quantity=_required(to_decimal(row.get("Volume"), "Volume"), "wolumen pozycji"),
        open_price=_required(to_decimal(row.get("Open price"), "Open price"), "cena otwarcia"),
        opened_at=_required(to_utc(row.get("Open time (UTC)"), "Open time (UTC)"), "czas otwarcia"),
        current_price=to_decimal(row.get("Current price"), "Current price"),
        value=to_decimal(row.get("Value"), "Value"),
        net_profit=to_decimal(row.get("Net Profit"), "Net Profit"),
        net_profit_pct=to_decimal(row.get("Net Profit %"), "Net Profit %"),
        gross_profit=to_decimal(row.get("Gross Profit"), "Gross Profit"),
        stop_loss=to_decimal(row.get("Stop Loss"), "Stop Loss"),
        take_profit=to_decimal(row.get("Take Profit"), "Take Profit"),
        margin=to_decimal(row.get("Margin"), "Margin"),
        open_commission=to_decimal(row.get("Open Commission"), "Open Commission"),
        swap=to_decimal(row.get("Swap"), "Swap"),
        rollover=to_decimal(row.get("Rollover"), "Rollover"),
        raw=jsonable(row),
    )


def _closed_lot(row: dict[str, Any]) -> ClosedLot:
    return ClosedLot(
        xtb_position_id=_required(to_text(row.get("Position ID")), "numer pozycji"),
        ticker=_required(to_text(row.get("Ticker")), "ticker"),
        name=to_text(row.get("Instrument")),
        category=to_text(row.get("Category")),
        side=to_text(row.get("Type")) or "BUY",
        quantity=_required(to_decimal(row.get("Volume"), "Volume"), "wolumen pozycji"),
        open_price=_required(to_decimal(row.get("Open Price"), "Open Price"), "cena otwarcia"),
        opened_at=_required(to_utc(row.get("Open Time (UTC)"), "Open Time (UTC)"), "czas otwarcia"),
        close_price=to_decimal(row.get("Close Price"), "Close Price"),
        closed_at=to_utc(row.get("Close Time (UTC)"), "Close Time (UTC)"),
        close_origin=to_text(row.get("Close Origin")),
        commission=to_decimal(row.get("Commission"), "Commission"),
        swap=to_decimal(row.get("Swap"), "Swap"),
        rollover=to_decimal(row.get("Rollover"), "Rollover"),
        margin=to_decimal(row.get("Margin"), "Margin"),
        stop_loss=to_decimal(row.get("Stop Loss"), "Stop Loss"),
        take_profit=to_decimal(row.get("Take Profit"), "Take Profit"),
        open_conversion_rate=to_decimal(row.get("Open Conversion Rate"), "Open Conversion Rate"),
        close_conversion_rate=to_decimal(row.get("Close Conversion Rate"), "Close Conversion Rate"),
        raw=jsonable(row),
    )


def _account_summary(pre_rows: list[tuple[Any, ...]]) -> tuple[AccountSummaryRow, ...]:
    rows: list[AccountSummaryRow] = []
    inside = False
    for row in pre_rows:
        cells = tuple(row[:4]) + (None,) * (4 - len(row[:4]))
        if cells == ACCOUNT_SUMMARY_HEADER:
            inside = True
            continue
        if not inside:
            continue
        if all(cell is None for cell in row):
            break
        rows.append(
            AccountSummaryRow(
                product=to_text(cells[0]),
                metric=to_text(cells[1]) or "",
                amount=to_decimal(cells[2], "Amount"),
                currency=to_text(cells[3]),
                raw=jsonable(dict(zip(ACCOUNT_SUMMARY_HEADER, cells, strict=True))),
            )
        )
    return tuple(rows)
