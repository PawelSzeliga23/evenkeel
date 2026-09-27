import csv
import datetime as dt
import io
import re
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

import httpx

from app.market.http import Sleep, ensure_ok, get_with_retry
from app.market.types import CpiPoint, ProviderError

# GUS page "Miesięczne wskaźniki cen towarów i usług konsumpcyjnych od 1982 roku"; the CSV file name
# carries a version number that changes with each release, so the link is read from the page.
PAGE_URL = (
    "https://stat.gov.pl/obszary-tematyczne/ceny-handel/wskazniki-cen/"
    "wskazniki-cen-towarow-i-uslug-konsumpcyjnych-pot-inflacja-/"
    "miesieczne-wskazniki-cen-towarow-i-uslug-konsumpcyjnych-od-1982-roku/"
)
CSV_LINK = re.compile(r"""href=["']([^"']*miesiecznewskaznikicen[^"']*\.csv)["']""", re.IGNORECASE)
YOY_PRESENTATION = "Analogiczny miesiąc poprzedniego roku = 100"
COUNTRY = "Polska"
COLUMNS = frozenset({"Jednostka terytorialna", "Sposób prezentacji", "Rok", "Miesiąc", "Wartość"})
HUNDRED = Decimal(100)


def find_csv_url(page_html: str, page_url: str = PAGE_URL) -> str:
    match = CSV_LINK.search(page_html)
    if match is None:
        raise ProviderError("GUS: CPI CSV link not found on the page")
    return urljoin(page_url, match.group(1))


def _decode(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("cp1250")  # the file GUS publishes today


def parse_cpi_csv(content: bytes) -> list[CpiPoint]:
    reader = csv.DictReader(io.StringIO(_decode(content), newline=""), delimiter=";")
    if not COLUMNS <= set(reader.fieldnames or []):
        raise ProviderError("GUS: unexpected CPI CSV columns")
    points: dict[dt.date, Decimal] = {}
    for row in reader:
        value = (row["Wartość"] or "").strip()
        if (row["Sposób prezentacji"] or "").strip() != YOY_PRESENTATION or (row["Jednostka terytorialna"] or "").strip() != COUNTRY:
            continue
        if not value:  # months not published yet
            continue
        try:
            month = dt.date(int(row["Rok"]), int(row["Miesiąc"]), 1)
            points[month] = Decimal(value.replace(",", ".")) - HUNDRED
        except (ValueError, InvalidOperation) as exc:
            raise ProviderError(f"GUS: bad CPI row {row['Rok']}-{row['Miesiąc']}: {value!r}") from exc
    if not points:
        raise ProviderError("GUS: no year-over-year CPI values in the CSV")
    return [CpiPoint(month, yoy) for month, yoy in sorted(points.items())]


class GusInflationProvider:
    name = "gus"

    def __init__(self, client: httpx.Client, *, sleep: Sleep = time.sleep) -> None:
        self.client = client
        self.sleep = sleep

    def cpi(self) -> list[CpiPoint]:
        page = ensure_ok(get_with_retry(self.client, PAGE_URL, sleep=self.sleep))
        csv_url = find_csv_url(page.text, str(page.url))
        return parse_cpi_csv(ensure_ok(get_with_retry(self.client, csv_url, sleep=self.sleep)).content)
