from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import User
from app.models.structure import Skill


async def get_or_create_default_user(db: AsyncSession) -> User:
    """Single-user mode for now (see design doc §12 open decisions).
    Returns the first user row, creating one if none exists yet.
    """
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(name="default", target_roles=[], target_companies=[])
        db.add(user)
        await db.flush()
    return user


async def get_or_create_skill(db: AsyncSession, canonical_name: str, display_name: str) -> Skill:
    stmt = (
        pg_insert(Skill)
        .values(name=display_name, canonical_name=canonical_name)
        .on_conflict_do_nothing(index_elements=["canonical_name"])
        .returning(Skill.id)
    )
    result = await db.execute(stmt)
    skill_id = result.scalar_one_or_none()

    if skill_id is None:
        existing = await db.execute(
            select(Skill).where(Skill.canonical_name == canonical_name)
        )
        return existing.scalar_one()

    return Skill(id=skill_id, name=display_name, canonical_name=canonical_name)