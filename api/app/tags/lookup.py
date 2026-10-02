"""Which tags a holding on an account has: the holding's own links plus those only on that account (plan 7f-1)."""
from collections import defaultdict

from sqlalchemy import func, select

from app.models import Tag, TagLink
from app.scoping import UserScope
from app.tags.schemas import TagOnOut


class TagLookup:
    def __init__(self, scope: UserScope) -> None:
        rows = scope.db.execute(select(TagLink, Tag).join(Tag, Tag.id == TagLink.tag_id)
                                .where(Tag.user_id == scope.user.id).order_by(func.lower(Tag.name), Tag.id))
        self._everywhere: dict[str, list[TagOnOut]] = defaultdict(list)
        self._on_account: dict[tuple[str, int], list[TagOnOut]] = defaultdict(list)
        self._savings: dict[int, list[TagOnOut]] = defaultdict(list)
        for link, tag in rows:
            key = f"i:{link.instrument_id}" if link.instrument_id is not None else (
                f"b:{link.bond_series}" if link.bond_series is not None else None)
            entry = TagOnOut(id=tag.id, name=tag.name, color=tag.color, link_id=link.id,
                             own=key is not None and link.account_id is not None)
            if key is None:
                self._savings[link.account_id].append(entry)  # type: ignore[index]  # has_target: account set
            elif link.account_id is None:
                self._everywhere[key].append(entry)
            else:
                self._on_account[(key, link.account_id)].append(entry)

    def on(self, key: str, account_id: int) -> list[TagOnOut]:
        if key.startswith("s:"):
            return list(self._savings.get(account_id, ()))
        found = [*self._everywhere.get(key, ()), *self._on_account.get((key, account_id), ())]
        return sorted(found, key=lambda t: (t.name.lower(), t.own))

    def ids(self, key: str, account_id: int) -> set[int]:
        return {t.id for t in self.on(key, account_id)}
