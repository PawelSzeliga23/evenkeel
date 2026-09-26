from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.config import Settings
from app.errors import ApiError
from app.main import create_app


class Payload(BaseModel):
    count: int


def _app_with_test_routes(settings: Settings) -> TestClient:
    app = create_app(settings)

    @app.get("/test/api-error")
    def raise_api_error() -> None:
        raise ApiError(418, "teapot", "Jestem czajnikiem.", {"x": 1})

    @app.post("/test/validate")
    def validate(payload: Payload) -> dict[str, int]:
        return {"count": payload.count}

    return TestClient(app)


def test_api_error_is_rendered_in_standard_format(settings: Settings) -> None:
    response = _app_with_test_routes(settings).get("/test/api-error")

    assert response.status_code == 418
    assert response.json() == {"code": "teapot", "message": "Jestem czajnikiem.", "details": {"x": 1}}


def test_validation_error_is_rendered_in_standard_format(settings: Settings) -> None:
    response = _app_with_test_routes(settings).post("/test/validate", json={"count": "dużo"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["message"] == "Nieprawidłowe dane."
    assert body["details"]["errors"][0]["loc"] == ["body", "count"]


def test_unknown_route_is_rendered_in_standard_format(settings: Settings) -> None:
    response = TestClient(create_app(settings)).get("/api/nie-ma-takiego")

    assert response.status_code == 404
    assert response.json() == {"code": "not_found", "message": "Nie znaleziono.", "details": {}}
