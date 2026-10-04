"""PATCH /api/me/preferences (plan 8a); GET is part of /api/auth/me."""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.models import Account
from app.preferences.schemas import PreferencesOut, PreferencesPatch
from app.scoping import UserScope, get_scope

router = APIRouter(prefix="/api/me", tags=["preferences"])


def preferences_of(scope: UserScope) -> PreferencesOut:
    """The stored preferences over the defaults; fixed accounts keep only the user's existing ones."""
    out = PreferencesOut.model_validate(scope.user.preferences or {})
    if out.accounts_fixed:
        own = set(scope.db.scalars(select(Account.id).where(Account.user_id == scope.user.id)))
        out.accounts_fixed = sorted(i for i in out.accounts_fixed if i in own)
    return out


@router.patch("/preferences", response_model=PreferencesOut)
def save_preferences(body: PreferencesPatch, scope: UserScope = Depends(get_scope)) -> PreferencesOut:
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if "accounts_fixed" in changes:
        for account_id in changes["accounts_fixed"]:
            scope.get_account(account_id)  # someone else's or a missing account: 404
        changes["accounts_fixed"] = sorted(set(changes["accounts_fixed"]))
    scope.user.preferences = {**(scope.user.preferences or {}), **changes}
    scope.db.commit()
    return preferences_of(scope)
