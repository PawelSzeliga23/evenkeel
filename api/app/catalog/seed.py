"""The starter catalog of popular instruments (spec 7b §1), read from data/catalog.csv by migration 0010."""
import csv
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).with_name("data") / "catalog.csv"
HELD_GROUP = "Twój portfel"
ADDED_GROUP = "Dodane przez Ciebie"
GROUPS = (
    "ETF: USA", "ETF: świat", "ETF: rynki wschodzące i Europa", "ETF: Polska", "Akcje USA", "Akcje GPW", "Surowce",
    ADDED_GROUP,
)


@dataclass(frozen=True)
class CatalogRow:
    xtb_ticker: str
    name: str
    category: str
    currency: str
    catalog_group: str
    accumulating: bool | None  # None for stocks and gold: nothing to accumulate


def catalog_rows() -> list[CatalogRow]:
    with DATA.open(encoding="utf-8", newline="") as file:
        return [
            CatalogRow(row["xtb_ticker"], row["name"], row["category"], row["currency"], row["catalog_group"],
                       None if row["accumulating"] == "" else row["accumulating"] == "true")
            for row in csv.DictReader(file)
        ]
