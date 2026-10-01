from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from app.catalog.seed import GROUPS, catalog_rows
from tests.conftest import API_DIR, TEST_DATABASE_URL


def _config() -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return config


def test_catalog_file_is_well_formed() -> None:
    rows = catalog_rows()

    assert len(rows) == 38
    assert len({row.xtb_ticker for row in rows}) == 38
    assert {row.catalog_group for row in rows} <= set(GROUPS)
    assert all(row.category in ("etf", "stock") for row in rows)
    assert next(row for row in rows if row.xtb_ticker == "EQQQ.DE").accumulating is False
    assert next(row for row in rows if row.xtb_ticker == "AAPL.US").accumulating is None


def test_migration_0010_flags_existing_and_adds_the_rest(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE instruments CASCADE"))
    command.downgrade(_config(), "0009")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO instruments (xtb_ticker, name, category, currency, price_symbol) "
                          "VALUES ('SXR8.DE', 'Moja nazwa', 'etf', 'EUR', 'SXR8.DE')"))

    command.upgrade(_config(), "head")

    with engine.connect() as conn:
        rows = {r.xtb_ticker: r for r in conn.execute(text("SELECT * FROM instruments"))}
    assert len(rows) == 38
    assert (rows["SXR8.DE"].name, rows["SXR8.DE"].in_catalog, rows["SXR8.DE"].catalog_group) == (
        "Moja nazwa", True, "ETF: USA")
    assert (rows["VWCE.DE"].in_catalog, rows["VWCE.DE"].accumulating, rows["VWCE.DE"].price_checked_at) == (
        True, True, None)
    assert rows["AAPL.US"].accumulating is None


def test_migration_0010_downgrade_removes_only_unused_catalog_rows(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE instruments CASCADE"))
    command.downgrade(_config(), "0009")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO instruments (xtb_ticker, name) VALUES ('SXR8.DE', 'Moja nazwa')"))
    command.upgrade(_config(), "head")

    command.downgrade(_config(), "0009")

    with engine.connect() as conn:
        assert conn.execute(text("SELECT xtb_ticker FROM instruments")).scalars().all() == ["SXR8.DE"]
    command.upgrade(_config(), "head")
