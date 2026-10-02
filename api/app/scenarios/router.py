"""Saved what-if scenarios (plan 7b): the owner's own only; another user's is a 404 like a missing one."""
from fastapi import APIRouter, Depends, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.analytics.metrics import Period
from app.models import Scenario
from app.scenarios.schemas import ScenarioIn, ScenarioOut, ScenarioPatch, ScenarioResultOut
from app.scenarios.service import check_instruments, plan_of, scenario_result
from app.scoping import AccountIds, DbId, UserScope, get_scope

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def stored(scenario: Scenario) -> ScenarioIn:
    return ScenarioIn.model_validate({"name": scenario.name, "base": scenario.base,
                                      "allocation": scenario.allocation, "steps": scenario.steps})


def _merged(scenario: Scenario, patch: ScenarioPatch) -> ScenarioIn:
    data = stored(scenario).model_dump(mode="json") | patch.model_dump(mode="json", exclude_unset=True)
    try:
        return ScenarioIn.model_validate(data)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from None


def _save(scope: UserScope, scenario: Scenario, body: ScenarioIn) -> Scenario:
    check_instruments(scope, body)
    data = body.model_dump(mode="json")
    scenario.name, scenario.base = data["name"], data["base"]
    scenario.allocation, scenario.steps = data["allocation"], data["steps"]
    scope.db.add(scenario)
    scope.db.commit()
    scope.db.refresh(scenario)
    return scenario


@router.get("", response_model=list[ScenarioOut])
def list_scenarios(scope: UserScope = Depends(get_scope)) -> list[Scenario]:
    return list(scope.db.scalars(scope.scenarios()))


@router.post("", response_model=ScenarioOut, status_code=201)
def create_scenario(body: ScenarioIn, scope: UserScope = Depends(get_scope)) -> Scenario:
    return _save(scope, Scenario(user_id=scope.user.id), body)


@router.post("/preview", response_model=ScenarioResultOut)
def preview_scenario(
    body: ScenarioIn, scope: UserScope = Depends(get_scope), account_ids: AccountIds = None, period: Period = "all",
) -> ScenarioResultOut:
    check_instruments(scope, body)
    return scenario_result(scope, plan_of(body), scope.account_filter(account_ids), period)


@router.get("/{scenario_id}", response_model=ScenarioOut)
def get_scenario(scenario_id: DbId, scope: UserScope = Depends(get_scope)) -> Scenario:
    return scope.get_scenario(scenario_id)


@router.patch("/{scenario_id}", response_model=ScenarioOut)
def update_scenario(scenario_id: DbId, patch: ScenarioPatch, scope: UserScope = Depends(get_scope)) -> Scenario:
    scenario = scope.get_scenario(scenario_id)
    return _save(scope, scenario, _merged(scenario, patch))


@router.delete("/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: DbId, scope: UserScope = Depends(get_scope)) -> Response:
    scope.db.delete(scope.get_scenario(scenario_id))
    scope.db.commit()
    return Response(status_code=204)


@router.get("/{scenario_id}/result", response_model=ScenarioResultOut)
def scenario_result_of(
    scenario_id: DbId, scope: UserScope = Depends(get_scope), account_ids: AccountIds = None,
    period: Period = "all",
) -> ScenarioResultOut:
    scenario = scope.get_scenario(scenario_id)
    return scenario_result(scope, plan_of(stored(scenario)), scope.account_filter(account_ids), period)
