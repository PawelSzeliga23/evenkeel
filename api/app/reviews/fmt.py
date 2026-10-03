"""Polish number, date and table formatting of the review package."""
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

NBSP = " "
MINUS = "−"
NONE = "—"
MONTHS = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]


def _decimal(value: Decimal, places: int) -> str:
    """Polish: NBSP between thousands, a comma for decimals, a real minus sign."""
    rounded = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    sign = MINUS if rounded < 0 else ""
    whole, _, fraction = f"{abs(rounded):f}".partition(".")
    grouped = f"{int(whole):,}".replace(",", NBSP)
    return f"{sign}{grouped},{fraction}" if places else f"{sign}{grouped}"


def money(value: Decimal | None) -> str:
    return NONE if value is None else f"{_decimal(value, 2)}{NBSP}zł"


def pct(value: Decimal | None) -> str:
    return NONE if value is None else f"{_decimal(value, 2)}{NBSP}%"


def number(value: Decimal | None, places: int = 4) -> str:
    if value is None:
        return NONE
    text = _decimal(value, places)
    return text.rstrip("0").rstrip(",") if "," in text else text


def date(value: dt.date | None) -> str:
    return NONE if value is None else value.strftime("%d.%m.%Y")


def table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "brak"
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(_cell(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)




def _cell(text: str) -> str:
    """One table cell on one line: a pipe would start a new column and a line break would end the row."""
    return " ".join(text.replace("|", "/").splitlines())
