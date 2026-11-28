"""A GitHub sync is saved even while the model can't be reached, and what was
skipped is done by a later sync. Real database and sync; GitHub and the model
are stubbed.
"""
import uuid
from datetime import datetime, timezone

import pytest
from openai import RateLimitError
from sqlalchemy import select

from app.models.github_analysis import GithubProjectAnalysis, GithubRepoAnalysisCache
from app.models.inference import SkillEvidence
from app.models.structure import Skill, SkillAlias
from app.services.github import github_sync
from tests.api.test_evidence import auth, run
from tests.api.test_job_library import new_user
from tests.llm_stub import api_error, model, reply  # noqa: F401 (model is a fixture)

ASSESSMENT = {"depth_label": "layered", "observations": ["app/ and tests/ are separate"], "confidence": "high"}


class FakeGithub:
    """The repositories GitHub reports, each with one commit hash."""

    def __init__(self):
        self.repos = {"alpha": "sha-a1", "beta": "sha-b1"}
        self.technologies = ["Python"]


@pytest.fixture
def github(monkeypatch):
    fake = FakeGithub()

    def returns(value):
        async def call(*args, **kwargs):
            return value() if callable(value) else value
        return call

    async def last_commit(client, username, repo_name, token):
        return {"sha": fake.repos[repo_name], "date": datetime.now(timezone.utc)}

    for name, value in {
        "fetch_repos": lambda: [{"name": n} for n in fake.repos],
        "fetch_languages": lambda: {"Python": 100},
        "fetch_commit_count_last_30d": 3,
        "fetch_readme_exists": True,
        "fetch_ci_config_exists": True,
        "fetch_repo_tree": lambda: ["app/main.py", "tests/test_main.py"],
        "fetch_repo_file": None,
        "fetch_repo_path_exists": False,
        "fetch_recent_commits": lambda: [],
        "fetch_pull_request_stats": lambda: {},
        "fetch_user_commit_count_capped": 0,
    }.items():
        monkeypatch.setattr(github_sync, name, returns(value))
    monkeypatch.setattr(github_sync, "fetch_last_commit_info", last_commit)
    monkeypatch.setattr(github_sync, "is_eligible_for_architecture_pass", lambda **kwargs: True)

    real_analyze = github_sync.analyze_repo

    def analyze(**kwargs):
        return {**real_analyze(**kwargs), "technologies": list(fake.technologies)}
    monkeypatch.setattr(github_sync, "analyze_repo", analyze)

    async def nothing(*args, **kwargs):
        return None
    monkeypatch.setattr("app.api.sync.trigger_identity_refresh", nothing)
    return fake


def sync(client, user):
    response = client.post("/sync/github", headers=auth(user.id), json={"username": "ivy", "token": "t"})
    assert response.status_code == 200, response.text[:400]
    return response.json()


def per_repo(table, user, column) -> dict:
    async def go(db):
        result = await db.execute(select(table.repo_name, column).where(table.user_id == user.id))
        return dict(result.all())
    return run(go)


def assessments(user):
    return per_repo(GithubProjectAnalysis, user, GithubProjectAnalysis.architecture_assessment)


def cached(user):
    return per_repo(GithubRepoAnalysisCache, user, GithubRepoAnalysisCache.architecture_assessment)


def github_skills(user) -> set[str]:
    async def go(db):
        result = await db.execute(
            select(Skill.canonical_name).join(SkillEvidence, SkillEvidence.skill_id == Skill.id)
            .where(SkillEvidence.user_id == user.id, SkillEvidence.source_type == "github_repo")
        )
        return set(result.scalars().all())
    return run(go)


def labels(requests) -> list[str]:
    return ["architecture" if "file_paths" in r["messages"][1]["content"] else "skills" for r in requests]


def unavailable():
    return api_error(RateLimitError, 429)


def test_the_sync_is_saved_while_the_model_is_unavailable(client, seeded, github, model):
    unseen = f"Tool{uuid.uuid4().hex[:10]}"
    github.technologies = ["Python", unseen]
    model.will(unavailable(), unavailable())
    user = new_user()

    result = sync(client, user)

    assert result["status"] == "success"
    assert assessments(user) == {"alpha": None, "beta": None}
    assert github_skills(user) == {"python"}
    assert cached(user) == {}  # so both are assessed again next time
    # One failed assessment is enough: the second repository isn't asked about.
    assert labels(model.requests) == ["architecture", "skills"]

    async def remembered(db):
        return await db.scalar(select(SkillAlias.raw_string).where(SkillAlias.raw_string == unseen.lower()))
    assert run(remembered) is None


def test_the_next_sync_does_what_was_skipped(client, seeded, github, model):
    unseen = f"Tool{uuid.uuid4().hex[:10]}"
    github.technologies = [unseen]
    model.will(unavailable(), unavailable())
    user = new_user()
    sync(client, user)

    model.will(ASSESSMENT, ASSESSMENT, {"results": [
        {"raw": unseen, "canonical": unseen.lower(), "is_valid_skill": True},
    ]})
    sync(client, user)  # no new commits

    assert [a["depth_label"] for a in assessments(user).values()] == ["layered", "layered"]
    assert [a["depth_label"] for a in cached(user).values()] == ["layered", "layered"]
    assert github_skills(user) == {unseen.lower()}


def test_one_unusable_answer_does_not_stop_the_other_repositories(client, seeded, github, model):
    cut_off = reply(ASSESSMENT, finish_reason="length")
    model.will(cut_off, cut_off, ASSESSMENT)  # two attempts at the first repository
    user = new_user()

    sync(client, user)

    saved = assessments(user)
    assert saved["alpha"] is None and saved["beta"]["depth_label"] == "layered"
    assert list(cached(user)) == ["beta"]


def test_an_earlier_assessment_is_kept_when_a_new_one_cannot_be_made(client, seeded, github, model):
    model.will(ASSESSMENT, ASSESSMENT)
    user = new_user()
    sync(client, user)

    github.repos["alpha"] = "sha-a2"  # a new commit
    model.will(unavailable())
    sync(client, user)

    assert assessments(user)["alpha"]["depth_label"] == "layered"
    # The cache still points at the old commit, so the new one is assessed later.
    async def sha(db):
        return await db.scalar(select(GithubRepoAnalysisCache.last_commit_sha).where(
            GithubRepoAnalysisCache.user_id == user.id, GithubRepoAnalysisCache.repo_name == "alpha"))
    assert run(sha) == "sha-a1"

    model.will(ASSESSMENT)
    sync(client, user)
    assert run(sha) == "sha-a2"


def test_repositories_that_need_no_assessment_are_cached_as_before(client, seeded, github, model, monkeypatch):
    monkeypatch.setattr(github_sync, "is_eligible_for_architecture_pass", lambda **kwargs: False)
    user = new_user()

    sync(client, user)

    assert cached(user) == {"alpha": None, "beta": None}
    assert model.requests == []
