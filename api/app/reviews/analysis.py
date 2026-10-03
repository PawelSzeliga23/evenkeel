"""The Analiza screens in the review package (plan 7g): tags, the holdings' gains, income and costs — built by the
same functions as the screens, so the numbers match the app."""
from app.analytics.holdings import KINDS as HOLDING_KINDS
from app.analytics.holdings import holdings
from app.analytics.income import income
from app.analytics.schemas import GroupGainOut
from app.analytics.tags import tag_analytics
from app.reviews.fmt import MONTHS, NONE, date, money, pct, table
from app.scoping import UserScope
from app.tags.lookup import TagLookup

NO_TAGS = "Brak tagów."
OVERLAP = "Walor może mieć kilka tagów, więc udziały mogą sumować się do ponad 100 %."


def tag_names(lookup: TagLookup, key: str, account_id: int) -> str:
    """The holding's tags as its details show them, each once; „—” without any."""
    names = dict.fromkeys(tag.name for tag in lookup.on(key, account_id))
    return ", ".join(names) or NONE


def tags_section(scope: UserScope, account_ids: frozenset[int] | None) -> str:
    report = tag_analytics(scope, account_ids, "all")
    if not report.tags:
        return NO_TAGS
    rows = [[t.name, money(t.value_pln), pct(t.share_pct), money(t.gain_pln), pct(t.gain_pct), str(t.holdings)]
            for t in report.tags]
    if report.untagged is not None:
        u = report.untagged
        rows.append(["Bez tagu", money(u.value_pln), pct(u.share_pct), money(u.gain_pln), pct(u.gain_pct),
                     str(u.holdings)])
    if report.cash.value_pln:
        rows.append(["Gotówka", money(report.cash.value_pln), pct(report.cash.share_pct), NONE, NONE, NONE])
    return table(["Tag", "Wartość", "Udział w portfelu", "Zysk (cały okres)", "Zysk %", "Walorów"], rows) + "\n\n" + OVERLAP


NO_DATA = "Brak danych."
PERIODS = (("1m", "1 mies."), ("1y", "1 rok"), ("all", "cały okres"))
SOURCE_KINDS = {"savings": "konto oszczędnościowe", "bond": "obligacje", "xtb_interest": "odsetki XTB",
                "dividend": "dywidenda"}


def month_label(month: str) -> str:
    """"2026-09" → "wrz 2026"."""
    year, number = month.split("-")
    return f"{MONTHS[int(number) - 1]} {year}"


def _groups(groups: list[GroupGainOut], name: str) -> str:
    return table([name, "Wartość", "Zysk", "Zysk %"],
                 [[g.name, money(g.value_pln), money(g.gain_pln), pct(g.gain_pct)] for g in groups])


def holdings_section(scope: UserScope, account_ids: frozenset[int] | None) -> str:
    """Walory (7c): every holding's gain over 1 month, 1 year and the whole history, ranked by the last; and the whole
    history by account and by kind."""
    reports = {period: holdings(scope, account_ids, period) for period, _ in PERIODS}
    whole = reports["all"]
    if not whole.items:
        return NO_DATA
    found = {period: {item.key: item for item in report.items} for period, report in reports.items()}
    rows = []
    for item in sorted(whole.items, key=lambda i: i.gain_pln, reverse=True):
        row = [f"{item.ticker} — {item.name}" if item.ticker else item.name,
               HOLDING_KINDS.get(item.category, item.category), money(item.value_pln)]
        for period, _ in PERIODS:
            other = found[period].get(item.key)
            row += [money(other.gain_pln), pct(other.gain_pct)] if other else [NONE, NONE]
        rows.append(row)
    ranges = "; ".join(f"{name}: {date(reports[period].period.start)}–{date(reports[period].period.end)}"
                       for period, name in PERIODS if reports[period].period is not None)
    return "\n\n".join([
        "### Ranking walorów",
        table(["Walor", "Typ", "Wartość", "Zysk 1 mies.", "%", "Zysk 1 rok", "%", "Zysk cały okres", "%"], rows),
        f"Okresy — {ranges}.",
        "### Według kont", _groups(whole.by_account, "Konto"),
        "### Według typów", _groups(whole.by_kind, "Typ"),
    ])


def income_section(scope: UserScope, account_ids: frozenset[int] | None) -> str:
    """Dochód i koszty (7d): totals over 12 months and the whole history, the sources and costs of the whole history,
    and the last 12 months."""
    year, whole = income(scope, account_ids, "12m"), income(scope, account_ids, "all")
    if whole.period is None:
        return NO_DATA
    totals = [[name, money(t.income_pln), money(t.costs_pln), money(t.balance_pln)]
              for name, t in (("Ostatnie 12 miesięcy", year.totals), ("Cały okres", whole.totals))]
    return "\n\n".join([
        "### Suma", table(["Okres", "Dochód", "Koszty", "Bilans"], totals),
        "### Źródła dochodu (cały okres)",
        table(["Źródło", "Rodzaj", "Brutto", "Podatek", "Netto"],
              [[s.name, SOURCE_KINDS.get(s.kind, s.kind), money(s.gross_pln), money(s.tax_pln), money(s.net_pln)]
               for s in whole.sources]),
        "### Koszty (cały okres)",
        table(["Koszt", "Kwota", "Liczba"], [[c.name, money(c.amount_pln), str(c.count)] for c in whole.costs]),
        "### Miesiące (ostatnie 12)",
        table(["Miesiąc", "Odsetki", "Dywidendy", "Przewalutowanie", "Podatki", "Opłaty", "Bilans"],
              [[month_label(m.month), money(m.interest_pln), money(m.dividends_pln), money(m.fx_pln),
                money(m.taxes_pln), money(m.fees_pln), money(m.balance_pln)] for m in year.months]),
    ])
