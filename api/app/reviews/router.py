"""Claude reviews (spec 2026-10-02): the package to paste into claude.ai, and the answers pasted back (own only;
another user's is a 404 like a missing one)."""
from fastapi import APIRouter, Depends, Response
from fastapi.exceptions import RequestValidationError

from app.errors import ApiError
from app.models import AiReview
from app.reviews.clean import clean, count_sections
from app.reviews.package import build_package
from app.reviews.schemas import MAX_CONTENT, ReviewIn, ReviewListItem, ReviewOut
from app.scoping import AccountIds, DbId, UserScope, get_scope
from app.valuation.service import local_today

router = APIRouter(prefix="/api/reviews", tags=["reviews"])
WHOLE = "Cały portfel"


@router.get("/package")
def get_package(scope: UserScope = Depends(get_scope), account_ids: AccountIds = None) -> Response:
    today = local_today()
    text = build_package(scope, scope.account_filter(account_ids), today)
    return Response(text, media_type="text/markdown; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="evenkeel-przeglad-{today.isoformat()}.md"',
    })


@router.get("", response_model=list[ReviewListItem])
def list_reviews(scope: UserScope = Depends(get_scope)) -> list[AiReview]:
    return list(scope.db.scalars(scope.reviews()))


@router.post("", response_model=ReviewOut, status_code=201)
def save_review(body: ReviewIn, scope: UserScope = Depends(get_scope)) -> AiReview:
    content = clean(body.content)
    if not content:
        raise RequestValidationError([{"loc": ["body", "content"], "msg": "Wklej odpowiedź Claude.", "type": "missing"}])
    if len(content) > MAX_CONTENT:
        raise ApiError(422, "review_too_long", f"Przegląd jest za długi (najwyżej {MAX_CONTENT:,} znaków).".replace(",", " "))
    chosen = scope.account_filter(body.account_ids)
    label = WHOLE if chosen is None else ", ".join(a.name for a in scope.db.scalars(scope.accounts()) if a.id in chosen)
    review = AiReview(user_id=scope.user.id, account_ids=sorted(chosen or []), account_label=label[:300],
                      content=content, sections=count_sections(content))
    scope.db.add(review)
    scope.db.commit()
    scope.db.refresh(review)
    return review


@router.get("/{review_id}", response_model=ReviewOut)
def get_review(review_id: DbId, scope: UserScope = Depends(get_scope)) -> AiReview:
    return scope.get_review(review_id)


@router.delete("/{review_id}", status_code=204)
def delete_review(review_id: DbId, scope: UserScope = Depends(get_scope)) -> Response:
    scope.db.delete(scope.get_review(review_id))
    scope.db.commit()
    return Response(status_code=204)
