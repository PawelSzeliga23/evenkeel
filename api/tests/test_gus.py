import datetime as dt
from decimal import Decimal

import httpx
import pytest

from app.market.http import make_client
from app.market.providers.gus import PAGE_URL, GusInflationProvider, find_csv_url, parse_cpi_csv
from app.market.types import ProviderError

CSV_PATH = "/download/gfx/portalinformacyjny/pl/defaultstronaopisowa/4741/1/1/miesiecznewskaznikicentowarowiuslugkonsumpcyjnychod1982roku_8.csv"
PAGE = f'<html><body><a href="{CSV_PATH.replace(".csv", ".xlsx")}">XLSX</a> <a href="{CSV_PATH}">CSV</a></body></html>'
HEADER = "Nazwa zmiennej;Jednostka terytorialna;Sposób prezentacji;Rok;Miesiąc;Wartość;Flaga;;"
NAME = "Wskaźnik cen towarów i usług konsumpcyjnych"
YOY = "Analogiczny miesiąc poprzedniego roku = 100"


def _row(presentation: str, year: int, month: int, value: str, flag: str = "") -> str:
    return f"{NAME};Polska;{presentation};{year};{month};{value};{flag};;"


def _csv(encoding: str = "cp1250") -> bytes:
    lines = [
        HEADER,
        _row("Grudzień poprzedniego roku = 100", 2026, 8, "102,0"),
        _row(YOY, 2026, 7, "103,0"),
        _row(YOY, 2026, 8, "103,4"),
        _row(YOY, 2026, 9, ""),
        _row(YOY, 2002, 1, "103,4", flag="a"),
        _row(YOY, 2003, 5, "99,1"),
        _row("Poprzedni miesiąc = 100", 2026, 8, "100,1"),
    ]
    return ("\r\n".join(lines) + "\r\n").encode(encoding)


def test_csv_link_is_found_and_made_absolute() -> None:
    assert find_csv_url(PAGE) == f"https://stat.gov.pl{CSV_PATH}"


def test_missing_csv_link_is_provider_error() -> None:
    with pytest.raises(ProviderError):
        find_csv_url("<html>strona w przebudowie</html>")


def test_only_year_over_year_rows_are_kept_as_percent_change() -> None:
    points = parse_cpi_csv(_csv())

    assert [(point.year_month, point.yoy) for point in points] == [
        (dt.date(2002, 1, 1), Decimal("3.4")),
        (dt.date(2003, 5, 1), Decimal("-0.9")),
        (dt.date(2026, 7, 1), Decimal("3.0")),
        (dt.date(2026, 8, 1), Decimal("3.4")),
    ]


def test_utf8_file_is_read_too() -> None:
    assert len(parse_cpi_csv(_csv("utf-8"))) == 4


def test_unexpected_columns_are_provider_error() -> None:
    with pytest.raises(ProviderError, match="columns"):
        parse_cpi_csv("Rok;Wartość\r\n2026;103,4\r\n".encode("cp1250"))


def test_file_without_values_is_provider_error() -> None:
    with pytest.raises(ProviderError):
        parse_cpi_csv((HEADER + "\r\n" + _row(YOY, 2026, 9, "") + "\r\n").encode("cp1250"))


def test_bad_number_is_provider_error() -> None:
    with pytest.raises(ProviderError):
        parse_cpi_csv((HEADER + "\r\n" + _row(YOY, 2026, 8, "b.d.") + "\r\n").encode("cp1250"))


def test_provider_follows_link_from_the_page() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.path.endswith(".csv"):
            return httpx.Response(200, content=_csv())
        return httpx.Response(200, text=PAGE)

    provider = GusInflationProvider(make_client(httpx.MockTransport(handler)), sleep=lambda _: None)

    assert provider.cpi()[-1].yoy == Decimal("3.4")
    assert seen == [PAGE_URL, f"https://stat.gov.pl{CSV_PATH}"]
