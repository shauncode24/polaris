"""The user's review of their own evidence: confirm, edit, hide.

A row the user has reviewed (review_state "confirmed" or "edited", or
hidden) is theirs: syncs and re-uploads must not overwrite it. Hidden rows
stay stored but are excluded from everything that reads the evidence.

Because a resume re-upload creates fresh rows, the user's decisions on the
earlier rows are carried over to the matching new ones (matched on
`dedupe_key`, which edits never change).
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Education, Experience, Project, UserSkillOverride
from app.models.structure import Skill
from app.services.evidence.state import touch_evidence
from app.services.projects.linking import normalize_name

# kind -> (model, fields the user may edit)
KINDS = {
    "projects": (Project, ("name", "description", "stack", "tagline")),
    "experiences": (Experience, ("role", "company", "stack", "bullets")),
    "education": (Education, ("institution", "degree", "field_of_study")),
}

_LIST_FIELDS = {"stack", "bullets"}
ACTIONS = ("confirm", "edit", "hide", "unhide")


class ReviewError(ValueError):
    """The requested review action is not valid for this item."""


def item_key(kind: str, row) -> str:
    """Stable identity of a row: the key fixed at creation, else derived
    from its current name (rows from before keys existed were never edited).
    """
    if row.dedupe_key:
        return row.dedupe_key
    if kind == "projects":
        return normalize_name(row.name)
    if kind == "experiences":
        return f"{normalize_name(row.role)}@{normalize_name(row.company)}"
    return f"{normalize_name(row.institution)}@{normalize_name(row.degree or '')}"


def _clean_fields(kind: str, fields: dict | None) -> dict:
    allowed = KINDS[kind][1]
    cleaned: dict = {}
    for name, value in (fields or {}).items():
        if name not in allowed:
            raise ReviewError(f"'{name}' cannot be edited on {kind}.")
        if name in _LIST_FIELDS:
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ReviewError(f"'{name}' must be a list of strings.")
            cleaned[name] = [v.strip() for v in value if v.strip()]
        else:
            if value is not None and not isinstance(value, str):
                raise ReviewError(f"'{name}' must be text.")
            cleaned[name] = value.strip() if isinstance(value, str) else value
        if name in ("name", "role", "company", "institution") and not cleaned[name]:
            raise ReviewError(f"'{name}' cannot be empty.")
    return cleaned


async def apply_review(
    db: AsyncSession, user_id, kind: str, item_id, action: str, fields: dict | None = None
):
    """Applies a review action to one of the user's rows; None if it isn't theirs."""
    if kind not in KINDS:
        raise ReviewError(f"Unknown kind '{kind}'.")
    if action not in ACTIONS:
        raise ReviewError(f"Unknown action '{action}'.")
    model = KINDS[kind][0]

    result = await db.execute(select(model).where(model.id == item_id, model.user_id == user_id))
    row = result.scalar_one_or_none()
    if row is None:
        return None

    if action == "edit":
        cleaned = _clean_fields(kind, fields)
        if not cleaned:
            raise ReviewError("No fields to edit.")
        row.dedupe_key = item_key(kind, row)  # pin identity before the name can change
        for name, value in cleaned.items():
            setattr(row, name, value)
        row.review_state = "edited"
    elif action == "confirm":
        if row.review_state == "auto":
            row.review_state = "confirmed"
    elif action == "hide":
        row.is_hidden = True
        if row.review_state == "auto":
            row.review_state = "confirmed"  # a hidden row is a user decision; keep it from being refreshed away
    elif action == "unhide":
        row.is_hidden = False

    await db.commit()
    await touch_evidence(db, user_id)
    await db.refresh(row)
    return row


async def set_skill_hidden(db: AsyncSession, user_id, canonical_name: str, hidden: bool) -> bool:
    """Hides or restores one skill. False if the skill doesn't exist."""
    result = await db.execute(select(Skill).where(Skill.canonical_name == canonical_name))
    skill = result.scalar_one_or_none()
    if skill is None:
        return False
    await db.merge(UserSkillOverride(
        user_id=user_id, skill_id=skill.id, is_hidden=hidden, updated_at=datetime.now(timezone.utc),
    ))
    await db.commit()
    await touch_evidence(db, user_id)
    return True


async def carry_over_reviews(db: AsyncSession, user_id, resume_id) -> int:
    """Gives the rows of a freshly uploaded resume the decisions the user
    already made about the same items on earlier uploads (hidden, confirmed,
    edited). Also fixes each new row's dedupe_key. Returns how many rows
    picked up a decision.
    """
    carried = 0
    for kind, (model, editable) in KINDS.items():
        new_rows = list(
            (await db.execute(select(model).where(model.user_id == user_id, model.resume_id == resume_id)))
            .scalars().all()
        )
        if not new_rows:
            continue

        reviewed_stmt = (
            select(model)
            .where(model.user_id == user_id)
            .where((model.resume_id != resume_id) | (model.resume_id.is_(None)))
            .where((model.review_state != "auto") | (model.is_hidden.is_(True)))
            .order_by(model.created_at.desc())
        )
        if kind == "projects":
            reviewed_stmt = reviewed_stmt.where(Project.source != "github")
        reviewed_by_key: dict[str, object] = {}
        for old in (await db.execute(reviewed_stmt)).scalars().all():
            reviewed_by_key.setdefault(item_key(kind, old), old)

        for row in new_rows:
            key = item_key(kind, row)
            row.dedupe_key = key
            old = reviewed_by_key.get(key)
            if old is None:
                continue
            row.is_hidden = old.is_hidden
            row.review_state = old.review_state
            if old.review_state == "edited":
                for name in editable:
                    setattr(row, name, getattr(old, name))
            carried += 1

    await db.commit()
    return carried


def dedupe_rows(kind: str, rows: list) -> list:
    """One row per item, the first seen wins. `rows` must already be
    ordered newest first. Hidden rows are kept; callers decide what to do.
    """
    seen: set[str] = set()
    unique = []
    for row in rows:
        key = item_key(kind, row)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def dedupe_visible(kind: str, rows: list) -> list:
    """One row per item (newest wins), then without the ones the user hid.
    Deduping first matters: hiding the newest copy of an item must not
    bring back an older copy of it from an earlier upload.
    """
    return [row for row in dedupe_rows(kind, rows) if not row.is_hidden]
