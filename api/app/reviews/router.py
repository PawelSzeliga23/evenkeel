"""Claude reviews (spec 2026-10-02): the package to paste into claude.ai."""
from fastapi import APIRouter, Depends, Response

from app.reviews.package import build_package
from app.scoping import AccountIds, UserScope, get_scope
from app.valuation.service import local_today

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("/package")
def get_package(scope: UserScope = Depends(get_scope), account_ids: AccountIds = None) -> Response:
    today = local_today()
    text = build_package(scope, scope.account_filter(account_ids), today)
    return Response(text, media_type="text/markdown; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="evenkeel-przeglad-{today.isoformat()}.md"',
    })
