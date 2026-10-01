"""Parameters of past EDO issues (plan 7b): one page per series on obligacjeskarbowe.pl, parsed once into
data/edo_series.csv, which migration 0011 loads. Older pages give the margin only in the issue letter (PDF),
read with pypdf, which the app itself does not need. Run once, in a throwaway container:
`pip install pypdf fonttools && python -m app.bonds.edo_history [--since 2016-01]`."""
import argparse
import csv
import datetime as dt
import html as html_lib
import re
import sys
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import httpx

from app.bonds.edo import series_name

DATA = Path(__file__).with_name("data") / "edo_series.csv"
PAGE_URL = "https://www.obligacjeskarbowe.pl/oferta-obligacji/obligacje-10-letnie-edo/{slug}/"
NUMBER = r"(\d+,\d+)"
# Two wordings: "…w pierwszym rocznym okresie odsetkowym wynosi 2,70%" and (from 2023) "Oprocentowanie: 7,25% w pierwszym…".
RATE = re.compile(r"pierwszym rocznym okresie odsetkowym wynosi\s*" + NUMBER + r"\s*%"
                  r"|Oprocentowanie:\s*" + NUMBER + r"\s*% w pierwszym rocznym")
MARGIN = re.compile(r"marża\s*" + NUMBER + r"\s*%")
FEE = re.compile(r"wynosi\s*" + NUMBER + r"\s*zł od każdej obligacji")
NEW_FEE = re.compile(r"zakupionych od 1 września 2024 r\. opłata wynosi\s*" + NUMBER + r"\s*zł")
NEW_FEE_FROM = dt.date(2024, 9, 1)
SITE = "https://www.obligacjeskarbowe.pl"
LETTER = re.compile(r'href="([^"]+\.pdf)"')
# In the letter's extracted text words come split ("mar żę w wysoko ści"), so it is searched with all spaces removed.
LETTER_MARGIN = re.compile(r"stałąmarżęwwysokości" + NUMBER + "%")
PAUSE_SECONDS = 0.5
# Series whose page sits at a misspelled address on the site (found by search, 2026-10-01).
SLUGS = {"EDO1028": "edo01028", "EDO1128": "edo01128", "EDO1228": "edo01228", "EDO0829": "edo07829"}


@dataclass(frozen=True)
class EdoIssue:
    series: str
    issue_month: dt.date
    first_period_rate: Decimal
    margin: Decimal
    early_redemption_fee: Decimal


def _text(page: str) -> str:
    """The page's visible text with tags dropped and whitespace (incl. &nbsp;) collapsed."""
    return re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", page))).strip()


def _number(pattern: re.Pattern[str], text: str, what: str) -> Decimal:
    found = pattern.search(text)
    if found is None:
        raise ValueError(f"no {what} on the page")
    return Decimal(next(group for group in found.groups() if group).replace(",", "."))


def page_slug(series: str) -> str:
    return SLUGS.get(series, series.lower())


def _fee(text: str, issue_month: dt.date | None) -> Decimal:
    """Pages since the 2024 change give two fees: until 31.08.2024 and from 1.09.2024; the issue date picks one."""
    if issue_month is not None and issue_month >= NEW_FEE_FROM and NEW_FEE.search(text):
        return _number(NEW_FEE, text, "early redemption fee")
    return _number(FEE, text, "early redemption fee")


def parse_series_page(page: str, issue_month: dt.date | None = None) -> tuple[Decimal, Decimal, Decimal]:
    """(first-year rate %, margin %, early redemption fee zł per bond) from a series page."""
    text = _text(page)
    return _number(RATE, text, "first-year rate"), _number(MARGIN, text, "margin"), _fee(text, issue_month)


def parse_letter_margin(text: str) -> Decimal:
    """The margin of years 2-10 from an issue letter's extracted text."""
    return _number(LETTER_MARGIN, re.sub(r"\s+", "", text), "margin in the issue letter")


def letter_url(page: str) -> str:
    found = LETTER.search(page)
    if found is None:
        raise ValueError("no issue letter link on the page")
    return found.group(1) if found.group(1).startswith("http") else SITE + found.group(1)


def _letter_text(client: httpx.Client, url: str) -> str:
    import io

    from pypdf import PdfReader  # only this one-off fetcher reads PDFs

    content = client.get(url).content
    return " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)


def issue_months(since: dt.date, until: dt.date) -> list[dt.date]:
    months, month = [], since.replace(day=1)
    while month <= until:
        months.append(month)
        month = (month + dt.timedelta(days=32)).replace(day=1)
    return months


def edo_issues() -> list[EdoIssue]:
    with DATA.open(encoding="utf-8", newline="") as file:
        return [
            EdoIssue(row["series"], dt.date.fromisoformat(row["issue_month"]), Decimal(row["first_period_rate"]),
                     Decimal(row["margin"]), Decimal(row["early_redemption_fee"]))
            for row in csv.DictReader(file)
        ]


def fetch(client: httpx.Client, months: list[dt.date]) -> list[EdoIssue]:
    """One page per month; any page that cannot be read stops the run naming its series (never a guessed row)."""
    issues, missing = [], []
    for month in months:
        series = series_name(month)
        response = client.get(PAGE_URL.format(slug=page_slug(series)))
        if response.status_code == 404:  # the site dropped a few old series pages: listed, never guessed
            missing.append(series)
            print(f"{series} {month:%Y-%m} BRAK STRONY", file=sys.stderr)
            continue
        if response.status_code != 200:
            raise SystemExit(f"{series}: HTTP {response.status_code}")
        page = response.text
        try:
            try:
                rate, margin, fee = parse_series_page(page, month)
            except ValueError as exc:
                if "margin" not in str(exc):
                    raise
                text = _text(page)
                rate, fee = _number(RATE, text, "first-year rate"), _fee(text, month)
                margin = parse_letter_margin(_letter_text(client, letter_url(page)))
        except ValueError as exc:
            raise SystemExit(f"{series}: {exc}") from exc
        issues.append(EdoIssue(series, month, rate, margin, fee))
        print(f"{series} {month:%Y-%m} {rate}% marża {margin}% opłata {fee} zł", file=sys.stderr)
        time.sleep(PAUSE_SECONDS)
    if missing:
        raise SystemExit(f"No page for: {', '.join(missing)}")
    return issues


def write(issues: list[EdoIssue], path: Path = DATA) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["series", "issue_month", "first_period_rate", "margin", "early_redemption_fee"])
        for issue in issues:
            writer.writerow([issue.series, issue.issue_month.isoformat(), issue.first_period_rate, issue.margin,
                             issue.early_redemption_fee])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default="2016-01")
    args = parser.parse_args()
    since = dt.date.fromisoformat(args.since + "-01")
    with httpx.Client(headers={"User-Agent": "Mozilla/5.0 (Evenkeel)"}, timeout=20, follow_redirects=True) as client:
        write(fetch(client, issue_months(since, dt.date.today())))


if __name__ == "__main__":
    main()
