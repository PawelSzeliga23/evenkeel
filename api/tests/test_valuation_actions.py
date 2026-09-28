import datetime as dt
from decimal import Decimal as D

from app.valuation.actions import Action, resolve, winning
from app.valuation.engine import Conversion, Split

NVDA, NEW = 3, 4
JUN_10, JUL_01 = dt.date(2024, 6, 10), dt.date(2024, 7, 1)


def _action(id_: int, type_: str, source: str, day: dt.date = JUN_10, ratio: tuple[str, str] = ("1", "10"),
            target: int | None = None) -> Action:
    return Action(id_, NVDA, type_, day, D(ratio[0]), D(ratio[1]), target, source)


def test_xtb_wins_over_the_provider_and_a_manual_entry_over_both() -> None:
    provider, xtb = _action(1, "split", "provider"), _action(2, "split", "xtb", ratio=("1", "5"))
    manual = _action(3, "split", "manual", ratio=("1", "20"))

    assert winning([provider, xtb]) == {(NVDA, JUN_10): xtb}
    assert winning([manual, provider, xtb]) == {(NVDA, JUN_10): manual}


def test_suppress_hides_its_day_only() -> None:
    actions = [
        _action(1, "split", "provider"),
        _action(2, "suppress", "manual", ratio=("1", "1")),
        _action(3, "split", "provider", day=JUL_01, ratio=("1", "2")),
    ]

    assert resolve(actions) == ([Split(NVDA, JUL_01, D(1), D(2))], [])


def test_conversion_is_resolved_to_the_engine_input() -> None:
    conversion = _action(1, "conversion", "manual", ratio=("1", "2"), target=NEW)

    assert resolve([conversion]) == ([], [Conversion(NVDA, NEW, JUN_10, D(1), D(2))])
