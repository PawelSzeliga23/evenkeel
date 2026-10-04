"""Plan 8c: Ustawienia → Odświeżanie cen reads the worker's schedule and the user's last refresh."""
import datetime as dt
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, Instrument, Transaction, User


def test_the_schedule_is_the_workers_and_the_last_refresh_the_users(
    make_app: Callable[..., FastAPI], engine: Engine,
) -> None:
    client = TestClient(make_app(market_intraday_minutes=15, market_intraday_to="21:00"))
    password = "bardzo-tajne-haslo"
    client.post("/api/auth/register", json={"email": "anna@portfolio.dev", "password": password})
    token = client.post("/api/auth/login", json={"email": "anna@portfolio.dev", "password": password}).json()
    headers = {"Authorization": f"Bearer {token['access_token']}"}

    empty = client.get("/api/market/schedule", headers=headers)

    assert empty.status_code == 200, empty.text
    assert empty.json() == {"intraday_every_minutes": 15, "intraday_from": "09:00", "intraday_to": "21:00",
                            "daily_at": "23:00", "timezone": "Europe/Warsaw", "last_refreshed_at": None}

    checked = dt.datetime(2026, 10, 2, 12, 30, tzinfo=dt.UTC)
    with Session(engine) as db:
        user_id = db.scalar(select(User.id))
        account = Account(user_id=user_id, name="IKE", kind="broker")
        instrument = Instrument(xtb_ticker="CDR.PL", name="CD Projekt", price_checked_at=checked)
        db.add_all([account, instrument])
        db.flush()
        db.add(Transaction(account_id=account.id, instrument_id=instrument.id, type="buy", xtb_type="buy",
                           occurred_at=checked, amount=-100, currency="PLN", external_id="1", comment="", raw={}))
        db.commit()

    assert dt.datetime.fromisoformat(client.get("/api/market/schedule", headers=headers).json()["last_refreshed_at"]) \
        == checked
