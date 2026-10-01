import datetime as dt
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from app.bonds.edo_history import (
    edo_issues, issue_months, letter_url, page_slug, parse_letter_margin, parse_series_page,
)
from tests.conftest import API_DIR, TEST_DATABASE_URL

# The wording of obligacjeskarbowe.pl/oferta-obligacji/obligacje-10-letnie-edo/edo0427/ (checked 2026-10-01).
PAGE = """<html><body><div class="product">
<p>Oprocentowanie obligacji w pierwszym rocznym okresie odsetkowym wynosi <strong>2,70%</strong>.</p>
<p>W kolejnych okresach: <span>marża 1,50%&nbsp;+ inflacja</span>, z roczną kapitalizacją odsetek.</p>
<p>Za przedterminowy wykup pobierana jest opłata, która wynosi 2,00 zł od każdej obligacji dziesięcioletniej.</p>
</div></body></html>"""


def test_parse_reads_rate_margin_and_fee_through_markup() -> None:
    assert parse_series_page(PAGE) == (Decimal("2.70"), Decimal("1.50"), Decimal("2.00"))


def test_parse_refuses_a_page_without_the_rate() -> None:
    with pytest.raises(ValueError, match="first-year rate"):
        parse_series_page(PAGE.replace("w pierwszym rocznym okresie odsetkowym wynosi", "wynosi"))


def test_issue_months_run_month_by_month() -> None:
    assert issue_months(dt.date(2025, 11, 1), dt.date(2026, 2, 14)) == [
        dt.date(2025, 11, 1), dt.date(2025, 12, 1), dt.date(2026, 1, 1), dt.date(2026, 2, 1)]


def test_the_committed_history_covers_every_month_since_2016() -> None:
    issues = edo_issues()
    months = [issue.issue_month for issue in issues]

    assert months == issue_months(dt.date(2016, 1, 1), months[-1])
    assert months[-1] >= dt.date(2026, 10, 1)
    by_series = {issue.series: issue for issue in issues}
    assert (by_series["EDO0427"].first_period_rate, by_series["EDO0427"].margin,
            by_series["EDO0427"].early_redemption_fee) == (Decimal("2.70"), Decimal("1.50"), Decimal("2.00"))
    assert by_series["EDO0126"].first_period_rate == Decimal("2.50")
    assert all(Decimal("0.5") <= i.first_period_rate <= Decimal("10") and Decimal("0") <= i.margin <= Decimal("3")
               for i in issues)


def test_migration_0011_adds_missing_series_and_keeps_existing(engine: Engine) -> None:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE bond_series CASCADE"))
    command.downgrade(config, "0010")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO bond_series (series, bond_type, issue_month, maturity_months, first_period_rate, margin, "
            "early_redemption_fee, interest_mode, rate_basis) VALUES "
            "('EDO0427', 'EDO', '2017-04-01', 120, 9.99, 9.99, 9.99, 'capitalized', 'cpi')"))

    command.upgrade(config, "head")

    with engine.connect() as conn:
        rows = {r.series: r for r in conn.execute(text("SELECT * FROM bond_series"))}
    assert len(rows) == len(edo_issues())
    assert rows["EDO0427"].first_period_rate == Decimal("9.99")  # the owner's row is never overwritten
    assert (rows["EDO0126"].issue_month, rows["EDO0126"].maturity_months) == (dt.date(2016, 1, 1), 120)


# Older pages (e.g. EDO0126) give the margin only in the issue letter (PDF); its extracted text splits words.
LETTER = ("powi ększonej, w pierwszym okresie odsetkowym o mar żę w wysoko ści 2,50%, za ś w nast ępnych rocznych "
          "okresach odsetkowych o stał ą mar żę w wysoko ści 1,50%. 13. Sposób oblicz")


def test_letter_margin_is_read_through_split_words() -> None:
    assert parse_letter_margin(LETTER) == Decimal("1.50")


def test_page_without_margin_reports_it_so_the_letter_is_used() -> None:
    page = PAGE.replace("marża 1,50%&nbsp;+ inflacja", "suma inflacji i marży odsetkowej")
    with pytest.raises(ValueError, match="margin"):
        parse_series_page(page)
    assert letter_url(page.replace("</div>", '<a href="/media_files/abc.pdf">Zobacz list emisyjny</a></div>')) == (
        "https://www.obligacjeskarbowe.pl/media_files/abc.pdf")


def test_parse_reads_the_rate_given_up_front() -> None:
    page = PAGE.replace("Oprocentowanie obligacji w pierwszym rocznym okresie odsetkowym wynosi <strong>2,70%</strong>.",
                        "Oprocentowanie: 7,25% w pierwszym rocznym okresie odsetkowym, w kolejnych")
    assert parse_series_page(page)[0] == Decimal("7.25")


def test_misspelled_series_pages_are_known() -> None:
    assert page_slug("EDO0829") == "edo07829"
    assert page_slug("EDO0427") == "edo0427"


TIERED = PAGE.replace(
    "opłata, która wynosi 2,00 zł od każdej obligacji dziesięcioletniej.",
    "opłata. Dla emisji zakupionych do 31 sierpnia 2024 r. opłata wynosi 2,00 zł od każdej obligacji dziesięcioletniej. "
    "Dla emisji zakupionych od 1 września 2024 r. opłata wynosi 3,00 zł od każdej obligacji dziesięcioletniej.")


def test_fee_follows_the_issue_date_when_the_page_gives_two() -> None:
    assert parse_series_page(TIERED, dt.date(2024, 8, 1))[2] == Decimal("2.00")
    assert parse_series_page(TIERED, dt.date(2024, 9, 1))[2] == Decimal("3.00")
    assert parse_series_page(PAGE, dt.date(2024, 9, 1))[2] == Decimal("2.00")
