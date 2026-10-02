"""The simulator's result (plan 7b): the blocks' pretend transactions valued in memory by the real engine, next to
the real portfolio's cached line, with the measures of `analytics.analyze` for both."""
import datetime as dt
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select

from app.analytics.metrics import Day, Period, Rate, analyze, period_start
from app.analytics.service import measure_fields, nbp_rates
from app.bonds.edo import Series as BondTerms
from app.catalog.seed import ADDED_GROUP
from app.errors import ApiError
from app.models import BondSeries, Cpi, Instrument, User
from app.portfolio.service import daily_totals
from app.scenarios.schemas import (
    MeasuresOut, PointOut, RecurringStep, ReplaceStep, ScenarioIn, ScenarioResultOut, TargetIn,
)
from app.scenarios.simulate import (
    PORTFOLIO, PRETEND_ACCOUNT, InstrumentInfo, Plan, Recurring, Replace, Share, Target, World, instrument_targets,
    simulate, uses_bonds,
)
from app.scoping import UserScope
from app.valuation.engine import ZERO, daily_rows, money
from app.valuation.exit_costs import ExitRules
from app.valuation.fixed_income import bond_rows, savings_rows
from app.valuation.service import load_fixed_income, load_inputs


def _target(target: TargetIn) -> Target:
    return Target(target.instrument_id, target.bond)


def _month(text: str) -> dt.date:
    return dt.date(int(text[:4]), int(text[5:7]), 1)


def plan_of(body: ScenarioIn) -> Plan:
    steps: list[Replace | Recurring] = []
    for step in body.steps:
        if isinstance(step, ReplaceStep):
            steps.append(Replace(step.from_instrument_id, step.to_instrument_id))
        else:
            assert isinstance(step, RecurringStep)
            steps.append(Recurring(step.amount_pln, step.day_of_month, _month(step.start),
                                   _month(step.end) if step.end else None, _target(step.target), step.ike))
    return Plan(body.base, tuple(Share(_target(share.target), share.share_pct) for share in body.allocation),
                tuple(steps))


def check_instruments(scope: UserScope, body: ScenarioIn) -> None:
    """Every instrument of the scenario is in the catalog or in the owner's portfolio."""
    plan = plan_of(body)
    wanted = instrument_targets(plan) | {step.from_id for step in plan.steps if isinstance(step, Replace)}
    if not wanted:
        return
    held = set(scope.db.scalars(scope.instruments().with_only_columns(Instrument.id)))
    listed = set(scope.db.scalars(
        select(Instrument.id).where(Instrument.id.in_(wanted), Instrument.in_catalog.is_(True))))
    if not wanted <= held | listed:
        raise ApiError(422, "unknown_instrument", "Nie ma takiego instrumentu w katalogu ani w portfelu.")


def _instruments(scope: UserScope, ids: set[int]) -> dict[int, InstrumentInfo]:
    if not ids:
        return {}
    rows = scope.db.execute(select(Instrument.id, Instrument.xtb_ticker, Instrument.category, Instrument.accumulating,
                                   Instrument.catalog_group).where(Instrument.id.in_(ids)))
    # Curated rows without a policy are gold ETCs (nothing to pay); an added or held ETF with none may pay dividends.
    return {row.id: InstrumentInfo(row.xtb_ticker, row.category == "stock" or row.accumulating is False
                                   or (row.accumulating is None and row.catalog_group in (None, ADDED_GROUP)))
            for row in rows}


def _edo_series(scope: UserScope) -> dict[str, BondTerms]:
    return {series.series: BondTerms(series.first_period_rate, series.margin, series.early_redemption_fee)
            for series in scope.db.scalars(select(BondSeries).where(BondSeries.bond_type == "EDO"))}


def simulated_days(scope: UserScope, plan: Plan, account_ids: frozenset[int] | None,
                   real: Sequence[Day]) -> tuple[list[Day], list[str]]:
    """(day, payout value, net external flow) of the scenario up to the real line's last day, and its notes."""
    db = scope.db
    first, end = real[0][0], real[-1][0]
    since = min([first] + [step.start for step in plan.steps if isinstance(step, Recurring)])
    extra = instrument_targets(plan)
    inputs = load_inputs(scope, extra, since)
    fixed = load_fixed_income(scope)

    def chosen(account_id: int) -> bool:
        return account_ids is None or account_id in account_ids

    portfolio = plan.base == PORTFOLIO
    bonds = uses_bonds(plan)
    cpi = fixed.cpi if fixed.cpi or not bonds else dict(db.execute(select(Cpi.year_month, Cpi.yoy)).all())
    world = World(inputs.market, inputs.splits, _instruments(scope, extra), _edo_series(scope) if bonds else {},
                  cpi, end)
    entries = [entry for entry in inputs.entries if chosen(entry.account_id)] if portfolio else []
    flows = [] if portfolio else [(day, flow) for day, _, flow in real if flow]
    result = simulate(plan, world, entries, flows)

    rules = ExitRules(inputs.exit_rules.fee_accounts | {PRETEND_ACCOUNT}, inputs.exit_rules.spreads)
    rows = daily_rows(result.entries, inputs.splits, inputs.market, end, conversions=inputs.conversions,
                      exit_rules=rules)
    holdings = [holding for holding in fixed.holdings if chosen(holding.account_id)] if portfolio else []
    rows += bond_rows(holdings + result.holdings, cpi, since, end)
    if portfolio:
        rows += savings_rows([account for account in fixed.savings if chosen(account.account_id)], since, end)
    totals: dict[dt.date, tuple[Decimal, Decimal]] = {}
    for row in rows:
        value, flow = totals.get(row.day, (ZERO, ZERO))
        totals[row.day] = (value + row.value_pln - row.exit_cost_pln, flow + row.net_flow_pln)
    return [(day, *totals[day]) for day in sorted(totals)], result.notes


def _running(days: Sequence[Day]) -> dict[dt.date, tuple[Decimal, Decimal]]:
    """Day → (value, money put in so far)."""
    invested, result = ZERO, {}
    for day, value, flow in days:
        invested += flow
        result[day] = (value, invested)
    return result


def _points(real: Sequence[Day], simulated: Sequence[Day], start: dt.date) -> list[PointOut]:
    ours, theirs = _running(real), _running(simulated)
    points = []
    for day in sorted(ours.keys() | theirs.keys()):
        if day < start:
            continue
        own, other = ours.get(day), theirs.get(day)
        points.append(PointOut(
            date=day,
            portfolio_pln=money(own[0]) if own else None, scenario_pln=money(other[0]) if other else None,
            invested_pln=money(own[1]) if own else None, scenario_invested_pln=money(other[1]) if other else None,
        ))
    return points


def _measures(days: Sequence[Day], rates: list[Rate], period: Period) -> MeasuresOut | None:
    result = analyze(days, rates, period)
    if result is None:
        return None
    return MeasuresOut(**measure_fields(result), value_pln=money(days[-1][1]),
                       invested_pln=money(sum((flow for day, _, flow in days if day >= result.start), ZERO)))


def scenario_result(scope: UserScope, plan: Plan, account_ids: frozenset[int] | None,
                    period: Period) -> ScenarioResultOut:
    db = scope.db
    recalculating = db.scalar(select(User.valuations_stale_from).where(User.id == scope.user.id)) is not None
    real = daily_totals(scope, account_ids)
    if not real:
        return ScenarioResultOut(points=[], portfolio=None, scenario=None, notes=[], recalculating=recalculating)
    simulated, notes = simulated_days(scope, plan, account_ids, real)
    rates = nbp_rates(db)
    first = min(real[0][0], simulated[0][0]) if simulated else real[0][0]
    return ScenarioResultOut(
        points=_points(real, simulated, period_start(period, first, real[-1][0])),
        portfolio=_measures(real, rates, period), scenario=_measures(simulated, rates, period),
        notes=notes, recalculating=recalculating,
    )
