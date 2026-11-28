"""A LeetCode sync is saved even when the model can't classify a topic name it
hasn't seen; a later sync classifies it. Real database; the model is stubbed.
"""
import uuid

import pytest
from openai import RateLimitError
from sqlalchemy import select

from app.core.llm import LLMError
from app.models.facts import LeetcodeSnapshot
from app.models.inference import SkillEvidence
from app.models.structure import Skill, SkillAlias
from app.services.resume.skill_classifier import resolve_skills
from tests.api.test_evidence import auth, run
from tests.api.test_job_library import new_user
from tests.llm_stub import api_error, model  # noqa: F401 (model is a fixture)


@pytest.fixture(autouse=True)
def no_identity_refresh(monkeypatch):
    async def nothing(*args, **kwargs):
        return None
    monkeypatch.setattr("app.api.sync.trigger_identity_refresh", nothing)


@pytest.fixture
def unseen() -> str:
    return f"topic-{uuid.uuid4().hex[:12]}"


def submit(client, user, tags):
    return client.post("/sync/leetcode/manual", headers=auth(user.id), json={"tag_counts": tags})


def saved_counts(user) -> dict[str, int]:
    async def go(db):
        result = await db.execute(select(LeetcodeSnapshot.tag, LeetcodeSnapshot.solved_count)
                                  .where(LeetcodeSnapshot.user_id == user.id))
        return dict(result.all())
    return run(go)


def leetcode_skills(user) -> set[str]:
    async def go(db):
        result = await db.execute(
            select(Skill.canonical_name).join(SkillEvidence, SkillEvidence.skill_id == Skill.id)
            .where(SkillEvidence.user_id == user.id, SkillEvidence.source_type == "leetcode_tag")
        )
        return set(result.scalars().all())
    return run(go)


def remembered(name) -> bool:
    async def go(db):
        return await db.scalar(select(SkillAlias.raw_string).where(SkillAlias.raw_string == name)) is not None
    return run(go)


def test_the_sync_is_saved_when_a_new_topic_cannot_be_classified(client, seeded, model, unseen):
    user = new_user()
    model.will(api_error(RateLimitError, 429))

    response = submit(client, user, {"python": 12, unseen: 7})

    assert response.status_code == 200, response.text[:300]
    assert response.json()["status"] == "success"
    assert saved_counts(user) == {"python": 12, unseen: 7}
    assert leetcode_skills(user) == {"python"}
    assert not remembered(unseen)


def test_the_next_sync_classifies_what_was_skipped(client, seeded, model, unseen):
    user = new_user()
    skill = unseen.replace("-", "_")
    model.will(
        api_error(RateLimitError, 429),
        {"results": [{"raw": unseen, "canonical": skill, "is_valid_skill": True}]},
    )
    submit(client, user, {unseen: 7})

    response = submit(client, user, {unseen: 7})  # nothing new solved

    assert response.status_code == 200, response.text[:300]
    assert leetcode_skills(user) == {skill}
    assert remembered(unseen)


def test_an_online_sync_is_saved_too(client, seeded, model, unseen, monkeypatch):
    async def profile(username):
        return {"tag_counts": {unseen: 3}, "total_solved": 3}
    monkeypatch.setattr("app.services.leetcode.leetcode_sync.fetch_leetcode_profile", profile)
    user = new_user()
    model.will(api_error(RateLimitError, 429))

    response = client.post("/sync/leetcode", headers=auth(user.id), json={"username": "ivy"})

    assert response.status_code == 200, response.text[:300]
    assert response.json()["status"] == "success"
    assert saved_counts(user) == {unseen: 3}


def test_other_features_are_still_told_the_model_failed(seeded, model, unseen):
    model.will(api_error(RateLimitError, 429))

    async def go(db):
        await resolve_skills({unseen}, db)

    with pytest.raises(LLMError):
        run(go)
