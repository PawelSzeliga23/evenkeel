"""The Analiza screens in the review package (plan 7g): tags, the holdings' gains, income and costs — built by the
same functions as the screens, so the numbers match the app."""
from app.analytics.tags import tag_analytics
from app.reviews.fmt import NONE, money, pct, table
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
