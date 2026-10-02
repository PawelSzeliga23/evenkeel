"""Saved what-if scenarios (plan 7b): the owner's own only; another user's is a 404 like a missing one."""
from fastapi import APIRouter, Depends, Response
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.models import Scenario
from app.scenarios.schemas import ScenarioIn, ScenarioOut, ScenarioPatch
from app.scoping import DbId, UserScope, get_scope

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
