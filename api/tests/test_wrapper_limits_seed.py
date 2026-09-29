from decimal import Decimal

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text

from tests.conftest import API_DIR, TEST_DATABASE_URL

EXPECTED = {
    (2023, "ike"): Decimal("20805"), (2023, "ikze"): Decimal("8322"), (2023, "ikze_self_employed"): Decimal("12483"),
    (2024, "ike"): Decimal("23472"), (2024, "ikze"): Decimal("9388.80"),
    (2024, "ikze_self_employed"): Decimal("14083.20"),
    (2025, "ike"): Decimal("26019"), (2025, "ikze"): Decimal("10407.60"),
    (2025, "ikze_self_employed"): Decimal("15611.40"),
    (2026, "ikze"): Decimal("11304"), (2026, "ikze_self_employed"): Decimal("16956"),
}


def _rows(engine: Engine) -> dict[tuple[int, str], Decimal]:
    with engine.connect() as conn:
        return {(r.year, r.wrapper): r.limit_pln for r in conn.execute(text("SELECT * FROM wrapper_limits"))}


def test_migration_0008_seeds_the_statutory_limits_and_takes_them_back(engine: Engine) -> None:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE wrapper_limits"))
        conn.execute(text("INSERT INTO wrapper_limits (year, wrapper, limit_pln) VALUES (2026, 'ike', 28260)"))

    command.downgrade(config, "0007")
    assert _rows(engine) == {(2026, "ike"): Decimal("28260")}  # 0005's row is not 0008's to remove

    command.upgrade(config, "head")
    assert _rows(engine) == {**EXPECTED, (2026, "ike"): Decimal("28260")}
