"""Writes a synthetic XTB export for the web e2e test: `python -m tests.e2e_fixture` (inside the api-e2e container).

A PLN stock bought twice after two deposits, so the dashboard has a staircase of paid-in capital and the position
detail has two lots that agree with the Open Positions snapshot. Values are made up."""
from datetime import datetime
from pathlib import Path

from tests import xtb_factory as xf

OUT = Path(__file__).resolve().parents[1] / ".e2e"
NAME = xf.filename("IKE", "56216965")
FIRST = datetime(2026, 1, 6, 9, 30)
SECOND = datetime(2026, 3, 3, 9, 30)


def build() -> bytes:
    stock = {"instrument": "CD Projekt", "category": "STOCK"}
    return xf.build_report(
        cash=[
            xf.cash_row("IKE deposit", 5000.0, "2001", datetime(2026, 1, 5, 8, 0)),
            xf.buy_row("CDR.PL", "2", "250", -500.0, "2002", FIRST, "881", **stock),
            xf.cash_row("IKE deposit", 3000.0, "2003", datetime(2026, 3, 2, 8, 0)),
            xf.buy_row("CDR.PL", "1", "270", -270.0, "2004", SECOND, "882", **stock),
        ],
        open_rows=[
            xf.summary_row("CDR.PL", "CD Projekt", 3.0, 810.0, 256.67, 40.0, category="STOCK"),
            xf.lot_row("CDR.PL", "881", 2.0, 250.0, FIRST, 270.0, 540.0, 40.0),
            xf.lot_row("CDR.PL", "882", 1.0, 270.0, SECOND, 270.0, 270.0, 0.0),
        ],
    )


def main() -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / NAME).write_bytes(build())
    print(OUT / NAME)


if __name__ == "__main__":
    main()
