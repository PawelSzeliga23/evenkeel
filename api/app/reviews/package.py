"""The Claude review package (spec 2026-10-02 §2): the instructions and the portfolio's data as one Markdown file.

Every number comes from the services behind the screens (Pulpit, Pozycje, Analiza, limits, closed, simulator), so
the package says what the app says. Account numbers, the e-mail and database ids never go in.
"""
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from app.analytics.service import portfolio_analytics
from app.bonds.service import bond_detail
from app.models import Account, BondHolding, JournalEntry, SavingsAccount, SavingsRate
from app.notes.keys import key_of
from app.portfolio.closed import closed_investments
from app.portfolio.exposure import currency_exposure
from app.portfolio.limits import wrapper_limits
from app.portfolio.schemas import AllocationOut, PositionOut
from app.portfolio.service import average_price, build_positions, daily_totals, lot_outs, portfolio_summary
from app.reviews.prompt import INSTRUCTIONS
from app.scenarios.service import plan_of, scenario_result
from app.scoping import UserScope
from app.analytics.schemas import AnalyticsOut
from app.valuation.engine import Book
from app.valuation.service import load_fixed_income, load_inputs

NBSP = " "
MINUS = "−"
NONE = "—"
WRAPPERS = {"regular": "zwykłe", "ike": "IKE", "ikze": "IKZE"}
KINDS = {"broker": "maklerskie", "bonds": "obligacje", "savings": "oszczędnościowe", "cash": "gotówka"}
BASES = {"portfolio": "Mój portfel", "deposits": "Moje wpłaty"}
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
    lines += ["| " + " | ".join(cell.replace("|", "/") for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def _allocation(items: list[AllocationOut]) -> list[list[str]]:
    return [[item.name, money(item.value_pln), pct(item.share_pct)] for item in items]


def _accounts(scope: UserScope, account_ids: frozenset[int] | None) -> list[Account]:
    return [a for a in scope.db.scalars(scope.accounts()) if account_ids is None or a.id in account_ids]


def _positions(scope: UserScope, book: Book, items: list[PositionOut], today: dt.date) -> str:
    instruments = [p for p in items if p.kind == "instrument"]
    rows = [[
        p.ticker or NONE, p.name, p.category or NONE, p.account_name, p.currency or NONE, number(p.quantity),
        f"{number(p.price)} {p.price_currency or p.currency or ''}".strip() if p.price is not None else NONE,
        date(p.price_date), money(p.payout_pln), money(p.cost_pln), money(p.unrealized_pln), pct(p.unrealized_pct),
        money(p.price_effect_pln), money(p.fx_effect_pln), money(p.dividends_net_pln), pct(p.share_pct),
        money(p.day_change_pln), "cena z XTB" if "xtb_price" in p.flags else "",
    ] for p in instruments]
    out = [table(["Ticker", "Nazwa", "Rodzaj", "Konto", "Waluta", "Sztuk", "Cena bieżąca", "Z dnia",
                  "Wartość do wypłaty", "Koszt", "Zysk", "Zysk %", "Efekt ceny", "Efekt waluty", "Dywidendy netto",
                  "Udział", "Zmiana dnia", "Uwagi"], rows)]
    accounts = {a.id: a for a in scope.db.scalars(scope.accounts())}
    for p in instruments:
        if p.instrument_id is None:
            continue
        lots_out = lot_outs(scope.db, book, accounts[p.account_id], scope.get_instrument(p.instrument_id), today)
        lots = [[date(lot.opened_on), number(lot.quantity), f"{number(lot.open_price)} {p.currency or ''}".strip(),
                 f"{number(lot.open_price_with_fx)} {p.currency or ''}".strip() if lot.open_price_with_fx else NONE,
                 str(lot.holding_days)] for lot in lots_out]
        average = f"{number(average_price(lots_out))} {p.currency or ''}".strip()
        out.append(f"\n**Partie {p.ticker or p.name} ({p.account_name})** — średnia cena zakupu jak w XTB: {average}\n\n"
                   + table(["Data zakupu", "Sztuk", "Cena jak w XTB", "Z przewalutowaniem XTB", "Dni"], lots))
    return "\n".join(out)


def _bonds(scope: UserScope, items: list[PositionOut], today: dt.date) -> str:
    holdings = [p for p in items if p.kind == "bond" and p.bond_holding_id is not None]
    if not holdings:
        return "brak"
    fixed = load_fixed_income(scope)
    accounts = {a.id: a for a in scope.db.scalars(scope.accounts())}
    rows = []
    for p in holdings:
        stored = scope.db.scalar(scope.bond_holdings().where(BondHolding.id == p.bond_holding_id))
        if stored is None:
            continue
        detail = bond_detail(stored, accounts[stored.account_id], fixed, today)
        period = next((x for x in detail.periods if x.start <= today < x.end), None)
        rows.append([detail.bond.series, str(detail.bond.quantity), date(detail.bond.purchase_date),
                     pct(period.rate) if period else NONE, money(detail.bond.value_pln),
                     date(detail.bond.maturity_date), WRAPPERS[accounts[stored.account_id].wrapper]])
    return table(["Seria", "Sztuk", "Zakup", "Oprocentowanie teraz", "Wartość netto", "Wykup", "Konto"], rows)


def _savings(scope: UserScope, items: list[PositionOut], today: dt.date) -> str:
    rows = []
    for p in items:
        if p.kind != "savings" or p.savings_account_id is None:
            continue
        account = scope.db.get(SavingsAccount, p.savings_account_id)
        rate = scope.db.scalar(select(SavingsRate.annual_rate).where(
            SavingsRate.savings_account_id == p.savings_account_id, SavingsRate.valid_from <= today,
        ).order_by(SavingsRate.valid_from.desc()))
        rows.append([p.account_name, money(p.payout_pln), pct(rate), account.capitalization if account else NONE,
                     money(p.unrealized_pln)])
    return table(["Konto", "Saldo", "Oprocentowanie roczne", "Kapitalizacja", "Odsetki od wpłat"], rows)


def _measures(results: list[tuple[str, AnalyticsOut]]) -> str:
    rows = []
    for label, a in results:
        if a.period is None:
            continue
        fall = a.max_drawdown
        rows.append([
            label, f"{date(a.period.start)} – {date(a.period.end)}", money(a.profit_pln),
            pct(a.xirr.annual_pct if a.period.annualized else a.xirr.period_pct),
            pct(a.twr.annual_pct if a.period.annualized else a.twr.period_pct),
            "rocznie" if a.period.annualized else "za okres", pct(a.volatility_pct),
            NONE if a.sharpe is None else number(a.sharpe, 2),
            f"{pct(fall.pct)} ({date(fall.peak_date)} → {date(fall.trough_date)})" if fall else NONE,
            pct(a.current_drawdown_pct),
            f"{pct(a.best_day.pct)} ({date(a.best_day.date)})" if a.best_day else NONE,
            f"{pct(a.worst_day.pct)} ({date(a.worst_day.date)})" if a.worst_day else NONE,
        ])
    return table(["Okres", "Daty", "Zysk", "XIRR", "TWR", "Stopy", "Zmienność", "Sharpe", "Maks. obsunięcie",
                  "Obecne obsunięcie", "Najlepszy dzień", "Najgorszy dzień"], rows)


def _history(scope: UserScope, account_ids: frozenset[int] | None, whole: AnalyticsOut) -> str:
    month_end: dict[tuple[int, int], tuple[dt.date, Decimal, Decimal]] = {}
    invested = Decimal(0)
    for day, value, flow in daily_totals(scope, account_ids):
        invested += flow
        month_end[(day.year, day.month)] = (day, value, invested)
    rows = [[date(day), money(value), money(paid)] for day, value, paid in month_end.values()]
    grid = whole.monthly
    monthly = [[str(row.year)] + [pct(cell) if cell is not None else "" for cell in row.months] + [pct(row.year_pct)]
               for row in grid]
    return (table(["Koniec miesiąca", "Wartość", "Wpłacono łącznie"], rows) + "\n\n**Zwrot w miesiącach (TWR)**\n\n"
            + table(["Rok", *MONTHS, "Rok"], monthly))


def _limits(scope: UserScope, accounts: list[Account], today: dt.date) -> str:
    """The yearly limits (per person) of the wrappers among the chosen accounts only."""
    chosen = {account.wrapper for account in accounts}
    rows = [[limit.wrapper.upper(), str(limit.year), money(limit.paid_pln), money(limit.limit_pln),
             money(limit.remaining_pln), "tak" if limit.exceeded else "nie"]
            for limit in wrapper_limits(scope, today) if limit.year == today.year and limit.wrapper in chosen]
    return table(["Rodzaj", "Rok", "Wpłacono", "Limit", "Zostało", "Przekroczony"], rows)


def _closed(scope: UserScope, account_ids: frozenset[int] | None, today: dt.date) -> str:
    rows = [[c.ticker, c.name, c.account_name, "w całości" if c.status == "closed" else "częściowo",
             date(c.first_buy), date(c.last_sale), money(c.total_pln), pct(c.return_pct)]
            for c in closed_investments(scope, account_ids, today).investments]
    return table(["Ticker", "Nazwa", "Konto", "Sprzedane", "Pierwszy zakup", "Ostatnia sprzedaż",
                  "Wynik (z dywidendami)", "Wynik %"], rows)


def _scenarios(scope: UserScope, account_ids: frozenset[int] | None) -> str:
    from app.scenarios.router import stored  # the router owns turning a stored row into the validated body

    rows = []
    for scenario in scope.db.scalars(scope.scenarios()):
        result = scenario_result(scope, plan_of(stored(scenario)), account_ids, "all")
        if result.portfolio is None or result.scenario is None:
            continue
        ours, theirs = result.portfolio, result.scenario
        rows.append([scenario.name, BASES[scenario.base], money(theirs.value_pln),
                     money(theirs.value_pln - ours.value_pln),
                     pct(theirs.xirr.annual_pct if theirs.period.annualized else theirs.xirr.period_pct)])
    return table(["Scenariusz", "Punkt wyjścia", "Wartość scenariusza", "Różnica do portfela", "XIRR scenariusza"],
                 rows)


def _year_ago(today: dt.date) -> dt.date:
    try:
        return today.replace(year=today.year - 1)
    except ValueError:  # 29 February
        return today.replace(year=today.year - 1, day=28)


def _indent(text: str) -> str:
    """Further lines of a note indented, so the Markdown list item stays one item."""
    return text.replace("\r\n", "\n").replace("\n", "\n  ")


def _notes(scope: UserScope, items: list[PositionOut], today: dt.date) -> str:
    """The owner's theses of the holdings in the package and the journal of the last 12 months (spec 7f-2)."""
    short: dict[str, str] = {}
    long: dict[str, str] = {}
    for p in items:
        if p.kind == "instrument" and p.instrument_id is not None:
            key = f"i:{p.instrument_id}"
            short[key], long[key] = p.ticker or p.name, f"{p.ticker} — {p.name}" if p.ticker else p.name
        elif p.kind == "bond":
            short[f"b:{p.name}"] = long[f"b:{p.name}"] = p.name
        elif p.kind == "savings":
            short[f"s:{p.account_id}"] = long[f"s:{p.account_id}"] = p.account_name
    theses = sorted(
        ((long[key], thesis.body) for thesis in scope.db.scalars(scope.theses())
         if (key := key_of(thesis.instrument_id, thesis.bond_series, thesis.account_id)) in long),
        key=lambda pair: pair[0].casefold())
    entries = []
    for entry in scope.db.scalars(scope.journal().where(JournalEntry.entry_date >= _year_ago(today))):
        key = key_of(entry.instrument_id, entry.bond_series, entry.account_id)
        if key is None or key in short:
            entries.append((entry.entry_date, entry.id, "portfel" if key is None else short[key], entry.body))
    if not theses and not entries:
        return "Brak notatek."
    out = []
    if theses:
        out += ["### Tezy", "\n".join(f"- **{label}:** {_indent(body)}" for label, body in theses)]
    if entries:
        out += ["### Dziennik (ostatnie 12 miesięcy)",
                "\n".join(f"- {date(day)} · {label}: {_indent(body)}" for day, _, label, body in sorted(entries))]
    return "\n\n".join(out)


def build_package(scope: UserScope, account_ids: frozenset[int] | None, today: dt.date, notes: bool = True) -> str:
    accounts = _accounts(scope, account_ids)
    scope_label = "cały portfel" if account_ids is None else ", ".join(a.name for a in accounts)
    summary = portfolio_summary(scope, account_ids)
    book, items = build_positions(scope, load_inputs(scope), today, account_ids)
    whole, last_year = (portfolio_analytics(scope, account_ids, period) for period in ("all", "1y"))
    exposure = currency_exposure(scope, account_ids, today, today)
    by_account = {item.key: item for item in summary.by_account}

    parts = [INSTRUCTIONS, f"# Dane portfela (stan na {date(summary.as_of or today)}, konta: {scope_label})"]
    if summary.recalculating:
        parts.append("Uwaga: wycena była w trakcie przeliczania — liczby mogą się jeszcze zmienić.")
    parts += [
        "## Podsumowanie",
        table(["Miara", "Wartość"], [
            ["Wartość do wypłaty (po kosztach wyjścia)", money(summary.value_pln)],
            ["Wartość rynkowa", money(summary.market_value_pln)],
            ["Koszty wyjścia (przewalutowanie XTB itp.)", money(summary.exit_cost_pln)],
            ["Gotówka", money(summary.cash_pln)],
            ["Wpłacono", money(summary.invested_pln)],
            ["Zysk łącznie", f"{money(summary.total_gain_pln)} ({pct(summary.total_gain_pct)})"],
            ["Zmiana dnia", f"{money(summary.day_change_pln)} ({pct(summary.day_change_pct)})"],
            ["Dywidendy netto", money(summary.dividends_net_pln)],
            ["Odsetki netto", money(summary.interest_net_pln)],
            ["Opłaty", money(summary.fees_pln)],
            ["Stopa zwrotu TWR od początku", pct(summary.twr_pct)],
        ]),
        "## Konta",
        table(["Konto", "Typ", "Rodzaj", "Waluta", "Wartość", "Udział"], [
            [a.name, WRAPPERS[a.wrapper], KINDS[a.kind], a.currency,
             money(by_account[str(a.id)].value_pln) if str(a.id) in by_account else NONE,
             pct(by_account[str(a.id)].share_pct) if str(a.id) in by_account else NONE] for a in accounts
        ]),
        "## Pozycje (akcje i ETF-y)", _positions(scope, book, items, today),
        "## Obligacje", _bonds(scope, items, today),
        "## Konta oszczędnościowe", _savings(scope, items, today),
        "## Alokacja",
        "**Według rodzaju**\n\n" + table(["Rodzaj", "Wartość", "Udział"], _allocation(summary.by_kind)),
        "**Według waluty**\n\n" + table(["Waluta", "Wartość", "Udział"],
                                        [[c.currency, money(c.value_pln), pct(c.share_pct)] for c in exposure.current]),
        "**Według konta**\n\n" + table(["Konto", "Wartość", "Udział"], _allocation(summary.by_account)),
        "## Miary (Analiza)", _measures([("Cały okres", whole), ("Ostatni rok", last_year)]),
        "## Historia", _history(scope, account_ids, whole),
        f"## Limity IKE/IKZE ({today.year})", _limits(scope, accounts, today),
        "## Zamknięte inwestycje", _closed(scope, account_ids, today),
        *(["## Notatki właściciela", _notes(scope, items, today)] if notes else []),
        "## Scenariusze z Symulatora (cały okres)", _scenarios(scope, account_ids),
    ]
    return "\n\n".join(parts) + "\n"
