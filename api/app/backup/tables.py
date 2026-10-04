"""What a portfolio backup holds (plan 8c): one description of the tables for export and restore.

Every row keeps its `id` as a number inside the file; `refs` say which columns point at another table of the file.
Shared rows (instruments, bond series) are written only when the user's data refers to them and are matched by their
natural key on restore. The order of `TABLES` is the insert order.
"""
from dataclasses import dataclass, field

from sqlalchemy import ColumnElement, Select, select

from app.models import (
    Account,
    AiReview,
    CatalogAddition,
    BondHolding,
    CorporateAction,
    ImportRecord,
    JournalEntry,
    PositionLot,
    SavingsAccount,
    SavingsBalance,
    SavingsFlow,
    SavingsRate,
    Scenario,
    Tag,
    TagLink,
    Thesis,
    Transaction,
    XtbSnapshot,
)
from app.models.base import Base

FORMAT = "evenkeel-backup"
VERSION = 1


@dataclass(frozen=True)
class TableSpec:
    name: str
    model: type[Base]
    # column → table of the file it points at ("instruments" and "bond_series" are the shared tables)
    refs: dict[str, str] = field(default_factory=dict)
    # columns taken from the user on restore and left out of the file
    owner_column: str | None = None
    # filter of the user's own rows (besides `owner_column` or the account link)
    only: ColumnElement[bool] | None = None


def _accounts_of(user_id: int) -> Select[tuple[int]]:
    return select(Account.id).where(Account.user_id == user_id)


def _savings_of(user_id: int) -> Select[tuple[int]]:
    return select(SavingsAccount.id).where(SavingsAccount.account_id.in_(_accounts_of(user_id)))


ACCOUNT = {"account_id": "accounts"}
INSTRUMENT = {"instrument_id": "instruments"}
HOLDING = {"instrument_id": "instruments", "bond_series": "bond_series", "account_id": "accounts"}

TABLES: tuple[TableSpec, ...] = (
    TableSpec("accounts", Account, owner_column="user_id"),
    TableSpec("imports", ImportRecord, ACCOUNT, owner_column="user_id"),
    TableSpec("transactions", Transaction, {**ACCOUNT, **INSTRUMENT, "import_id": "imports",
                                            "transfer_pair_id": "transactions"}),
    TableSpec("position_lots", PositionLot, {**ACCOUNT, **INSTRUMENT}),
    TableSpec("xtb_snapshots", XtbSnapshot, {**ACCOUNT, **INSTRUMENT, "import_id": "imports"}),
    TableSpec("bond_holdings", BondHolding, {**ACCOUNT, "series": "bond_series"}),
    TableSpec("savings_accounts", SavingsAccount, ACCOUNT),
    TableSpec("savings_rates", SavingsRate, {"savings_account_id": "savings_accounts"}),
    TableSpec("savings_balances", SavingsBalance, {"savings_account_id": "savings_accounts"}),
    TableSpec("savings_flows", SavingsFlow, {"savings_account_id": "savings_accounts"}),
    TableSpec("tags", Tag, owner_column="user_id"),
    TableSpec("tag_links", TagLink, {"tag_id": "tags", **HOLDING}),
    TableSpec("theses", Thesis, HOLDING, owner_column="user_id"),
    TableSpec("journal_entries", JournalEntry, HOLDING, owner_column="user_id"),
    TableSpec("scenarios", Scenario, owner_column="user_id"),
    TableSpec("ai_reviews", AiReview, owner_column="user_id"),
    TableSpec("catalog_additions", CatalogAddition, INSTRUMENT, owner_column="user_id"),
    TableSpec("corporate_actions", CorporateAction, {**INSTRUMENT, "target_instrument_id": "instruments"},
              owner_column="user_id", only=CorporateAction.source == "manual"),
)
BY_NAME = {spec.name: spec for spec in TABLES}

# Shared tables: written with the rows that point at them, matched by this column on restore.
SHARED_KEYS = {"instruments": "xtb_ticker", "bond_series": "series"}
# Columns of shared rows that describe this server's state, not the instrument.
SHARED_VOLATILE = {"id", "created_at", "price_checked_at", "price_error"}

# Tables deliberately not in a backup: login data, shared market data and caches rebuilt from the backup.
NOT_BACKED_UP = {"users", "refresh_tokens", "prices", "fx_rates", "cpi", "nbp_ref_rates", "wrapper_limits",
                 "daily_valuations", "alembic_version"}


def user_rows(spec: TableSpec, user_id: int) -> Select[tuple[Base]]:
    """The user's rows of one table, oldest first."""
    model = spec.model
    statement = select(model)
    if spec.owner_column is not None:
        statement = statement.where(getattr(model, spec.owner_column) == user_id)
    elif "savings_account_id" in spec.refs:
        statement = statement.where(model.savings_account_id.in_(_savings_of(user_id)))  # type: ignore[attr-defined]
    elif spec.name == "tag_links":
        statement = statement.where(TagLink.tag_id.in_(select(Tag.id).where(Tag.user_id == user_id)))
    else:
        statement = statement.where(model.account_id.in_(_accounts_of(user_id)))  # type: ignore[attr-defined]
    if spec.only is not None:
        statement = statement.where(spec.only)
    return statement.order_by(model.id)  # type: ignore[attr-defined]
