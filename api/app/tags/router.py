"""Tags (plan 7f-1): the owner's own; someone else's tag, account or series is a 404 like a missing one."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.errors import ApiError
from app.models import BondHolding, SavingsAccount, Tag, TagLink
from app.scoping import DbId, UserScope, get_scope, not_found
from app.tags.schemas import PALETTE, TagIn, TagLinkIn, TagLinkOut, TagOut, TagPatch

router = APIRouter(prefix="/api", tags=["tags"])


def _clash(scope: UserScope, name: str, own_id: int | None = None) -> None:
    query = scope.tags().where(func.lower(Tag.name) == name.lower())
    if own_id is not None:
        query = query.where(Tag.id != own_id)
    if scope.db.scalar(query) is not None:
        raise ApiError(409, "tag_exists", f"Tag „{name}” już jest.")


def _commit_name(scope: UserScope, name: str) -> None:
    """Commits a new or renamed tag; the same name saved concurrently (any letter case) is the 409 `_clash` gives."""
    try:
        scope.db.commit()
    except IntegrityError:
        scope.db.rollback()
        raise ApiError(409, "tag_exists", f"Tag „{name}” już jest.") from None


def _existing_link(scope: UserScope, tag_id: int, body: TagLinkIn) -> TagLink | None:
    return scope.db.scalar(select(TagLink).where(
        TagLink.tag_id == tag_id, TagLink.instrument_id.is_not_distinct_from(body.instrument_id),
        TagLink.bond_series.is_not_distinct_from(body.bond_series),
        TagLink.account_id.is_not_distinct_from(body.account_id)))


def _out(scope: UserScope, tag: Tag) -> TagOut:
    links = scope.db.scalar(select(func.count()).select_from(TagLink).where(TagLink.tag_id == tag.id)) or 0
    return TagOut(id=tag.id, name=tag.name, color=tag.color, links=links)


def _bad_target(message: str) -> ApiError:
    return ApiError(422, "link_target", message)


@router.get("/tags", response_model=list[TagOut])
def list_tags(scope: UserScope = Depends(get_scope)) -> list[TagOut]:
    counts = dict(scope.db.execute(
        select(TagLink.tag_id, func.count()).join(Tag, Tag.id == TagLink.tag_id)
        .where(Tag.user_id == scope.user.id).group_by(TagLink.tag_id)).all())
    return [TagOut(id=t.id, name=t.name, color=t.color, links=counts.get(t.id, 0))
            for t in scope.db.scalars(scope.tags())]


@router.post("/tags", response_model=TagOut, status_code=201)
def create_tag(body: TagIn, scope: UserScope = Depends(get_scope)) -> TagOut:
    _clash(scope, body.name)
    count = scope.db.scalar(select(func.count()).select_from(Tag).where(Tag.user_id == scope.user.id)) or 0
    tag = Tag(user_id=scope.user.id, name=body.name, color=body.color or PALETTE[count % len(PALETTE)])
    scope.db.add(tag)
    _commit_name(scope, body.name)
    return _out(scope, tag)


@router.patch("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: DbId, body: TagPatch, scope: UserScope = Depends(get_scope)) -> TagOut:
    tag = scope.get_tag(tag_id)
    if body.name is not None:
        _clash(scope, body.name, tag.id)
        tag.name = body.name
    if body.color is not None:
        tag.color = body.color
    _commit_name(scope, tag.name)
    return _out(scope, tag)


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: DbId, scope: UserScope = Depends(get_scope)) -> Response:
    scope.db.delete(scope.get_tag(tag_id))
    scope.db.commit()
    return Response(status_code=204)


@router.post("/tags/{tag_id}/links", response_model=TagLinkOut, status_code=201)
def link_tag(tag_id: DbId, body: TagLinkIn, response: Response, scope: UserScope = Depends(get_scope)) -> TagLink:
    tag = scope.get_tag(tag_id)
    if body.instrument_id is not None and body.bond_series is not None:
        raise _bad_target("Tag przypina się do jednego waloru.")
    account = scope.get_account(body.account_id) if body.account_id is not None else None
    if body.instrument_id is not None:
        scope.get_instrument(body.instrument_id)
    elif body.bond_series is not None:
        bonds = scope.bond_holdings().where(BondHolding.series == body.bond_series)
        if account is not None:
            bonds = bonds.where(BondHolding.account_id == account.id)
        if scope.db.scalar(bonds) is None:
            raise not_found()
    elif account is None or scope.db.scalar(
            scope.savings_accounts().where(SavingsAccount.account_id == account.id)) is None:
        raise _bad_target("Tag bez waloru można przypiąć tylko do konta oszczędnościowego.")
    existing = _existing_link(scope, tag.id, body)
    if existing is not None:
        response.status_code = 200
        return existing
    link = TagLink(tag_id=tag.id, instrument_id=body.instrument_id, bond_series=body.bond_series,
                   account_id=body.account_id)
    scope.db.add(link)
    try:
        scope.db.commit()
    except IntegrityError:  # the same link was made concurrently: answer with it, as for a repeated link
        scope.db.rollback()
        existing = _existing_link(scope, tag.id, body)
        if existing is None:
            raise
        response.status_code = 200
        return existing
    return link


@router.delete("/tag-links/{link_id}", status_code=204)
def unlink_tag(link_id: DbId, scope: UserScope = Depends(get_scope)) -> Response:
    link = scope.db.scalar(select(TagLink).join(Tag, Tag.id == TagLink.tag_id)
                           .where(TagLink.id == link_id, Tag.user_id == scope.user.id))
    if link is None:
        raise not_found()
    scope.db.delete(link)
    scope.db.commit()
    return Response(status_code=204)
