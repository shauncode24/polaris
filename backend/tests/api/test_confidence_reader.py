"""Pins the database-backed confidence readers on one fixed scenario
(see confidence_seed.py). Numbers captured from the code before the
confidence modules were merged.
"""
import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.evidence.confidence import get_all_skill_confidences
from app.services.evidence.confidence import get_reconciled_skill_confidences
from tests.api.conftest import _new_engine
from tests.api.confidence_seed import seed_dana


def _run(seeded_dana, reader):
    async def go():
        engine = _new_engine()
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as db:
            result = await reader(db, seeded_dana["user_id"])
        await engine.dispose()
        return result
    return asyncio.run(go())


import pytest


@pytest.fixture(scope="module")
def dana(seeded):
    async def go():
        engine = _new_engine()
        ids = await seed_dana(engine)
        await engine.dispose()
        return ids
    return asyncio.run(go())


def test_confidence_map_only_contains_skills_with_evidence(dana):
    result = _run(dana, get_all_skill_confidences)
    assert set(result) == {"python", "docker", "go"}  # rust has no evidence
    assert result["python"] == pytest.approx(0.5175)   # (0.35 + 0.10) * 1.15 corroboration bonus
    assert result["docker"] == pytest.approx(0.175)    # 400-day-old evidence, x0.5
    assert result["go"] == pytest.approx(0.10)


def test_reconciled_map_carries_sources_and_corroboration(dana):
    result = _run(dana, get_reconciled_skill_confidences)
    assert set(result) == {"python", "docker", "go"}
    python = result["python"]
    assert python["confidence"] == 0.52 and python["raw_confidence"] == 0.52
    assert python["corroboration_count"] == 2
    assert python["sources"] == ["Project: Dana Project", "LeetCode practice history"]
    assert python["confidence_flags"] == []
    assert result["docker"]["confidence"] == 0.17
    assert result["go"]["sources"] == ["LeetCode practice history"]


def test_other_users_evidence_never_leaks_in(dana, seeded):
    alice = _run({"user_id": seeded["alice_id"]}, get_all_skill_confidences)
    assert not {"python", "docker", "go"} & set(alice)


def test_a_hidden_skill_disappears_from_every_confidence_reader(dana):
    from app.models.facts import UserSkillOverride

    async def hide(skill_id, hidden):
        engine = _new_engine()
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as db:
            await db.merge(UserSkillOverride(user_id=dana["user_id"], skill_id=skill_id, is_hidden=hidden))
            await db.commit()
        await engine.dispose()

    asyncio.run(hide(dana["docker_id"], True))
    try:
        assert set(_run(dana, get_all_skill_confidences)) == {"python", "go"}
        assert set(_run(dana, get_reconciled_skill_confidences)) == {"python", "go"}
    finally:
        asyncio.run(hide(dana["docker_id"], False))
    assert "docker" in _run(dana, get_all_skill_confidences)
