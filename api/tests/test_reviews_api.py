from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, User
from app.reviews.clean import clean, count_sections
from app.reviews.prompt import SECTIONS

LoginAs = Callable[[str], dict[str, str]]
ANSWER = "\n\n".join(f"## {section}\n\nTreść." for section in SECTIONS)


def test_clean_strips_a_four_backtick_fence_and_prose_around_it() -> None:
    pasted = f"Oto przegląd:\n\n````markdown\n{ANSWER}\n````\n\nDaj znać, jeśli…"
    assert clean(pasted) == ANSWER


def test_clean_strips_a_three_backtick_fence_and_keeps_plain_text() -> None:
    assert clean(f"```markdown\n{ANSWER}\n```") == ANSWER
    assert clean(f"  {ANSWER}\n ") == ANSWER


def test_clean_keeps_inner_code_blocks_inside_a_four_backtick_fence() -> None:
    inner = "## Rynek\n\n```\nkod\n```\n\n## Źródła"
    assert clean(f"````markdown\n{inner}\n````") == inner


def test_sections_are_counted_whatever_the_case_or_an_emoji() -> None:
    assert count_sections(ANSWER) == 9
    assert count_sections("## 📊 ocena OGÓLNA\n\n## Ryzyka:\n\n### Rynek") == 2  # ### is not a section
    assert count_sections("zwykły tekst") == 0


@pytest.fixture
def anna(client: TestClient, login_as: LoginAs) -> dict[str, str]:
    return login_as("anna@portfolio.dev")


def test_save_list_read_and_delete(client: TestClient, anna: dict) -> None:
    created = client.post("/api/reviews", json={"content": f"````markdown\n{ANSWER}\n````"}, headers=anna)
    assert created.status_code == 201
    body = created.json()
    assert (body["content"], body["sections"], body["account_label"]) == (ANSWER, 9, "Cały portfel")

    listed = client.get("/api/reviews", headers=anna).json()
    assert [(r["id"], r["sections"]) for r in listed] == [(body["id"], 9)] and "content" not in listed[0]
    assert client.get(f"/api/reviews/{body['id']}", headers=anna).json()["content"] == ANSWER
    assert client.delete(f"/api/reviews/{body['id']}", headers=anna).status_code == 204
    assert client.get(f"/api/reviews/{body['id']}", headers=anna).status_code == 404


def test_label_names_the_chosen_accounts(client: TestClient, anna: dict, engine: Engine) -> None:
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        ike = Account(user_id=user_id, name="XTB IKE", kind="cash", currency="PLN")
        db.add(ike)
        db.commit()
        ike_id = ike.id

    body = client.post("/api/reviews", json={"content": ANSWER, "account_ids": [ike_id]}, headers=anna).json()

    assert body["account_label"] == "XTB IKE"


def test_reviews_of_another_user_are_not_found(client: TestClient, anna: dict, login_as: LoginAs) -> None:
    own = client.post("/api/reviews", json={"content": ANSWER}, headers=anna).json()
    bartek = login_as("bartek@portfolio.dev")

    assert client.get("/api/reviews", headers=bartek).json() == []
    assert client.get(f"/api/reviews/{own['id']}", headers=bartek).status_code == 404
    assert client.delete(f"/api/reviews/{own['id']}", headers=bartek).status_code == 404


def test_empty_or_too_long_content_is_422(client: TestClient, anna: dict) -> None:
    empty = client.post("/api/reviews", json={"content": "```markdown\n\n```"}, headers=anna)
    long = client.post("/api/reviews", json={"content": "x" * 200_001}, headers=anna)

    assert (empty.status_code, empty.json()["code"]) == (422, "validation_error")
    assert (long.status_code, long.json()["code"]) == (422, "review_too_long")


def test_a_code_block_inside_an_unwrapped_answer_keeps_the_whole_review() -> None:
    copied = "## Ocena ogólna\n\ntekst\n\n```\nkod\n```\n\n## Ryzyka\n\nwięcej"  # Copy in claude.ai drops the outer fence
    assert clean(copied) == copied
