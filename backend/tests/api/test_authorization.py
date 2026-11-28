"""Cross-user access: a user must never be able to read or change data
that belongs to someone else, whichever route they try it through.
"""
import asyncio
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.job_intelligence.builder import get_job_intelligence
from tests.api.conftest import _new_engine
from tests.authorization_cases import CASES


def _fill(value, ids):
    """Substitute {placeholders} in a path or JSON body with seeded ids."""
    if isinstance(value, str):
        return value.format(
            job_id=ids["job_id"], project_id=ids["project_id"], goal_id=ids["goal_id"],
            session_id=ids["session_id"], response_id=ids["response_id"], identity_id=ids["identity_id"],
            experience_id=ids["experience_id"], education_id=ids["education_id"],
            background_job_id=ids["background_job_id"],
        )
    if isinstance(value, dict):
        return {k: _fill(v, ids) for k, v in value.items()}
    return value


def _call(client, case, headers, ids):
    return client.request(
        case.method, _fill(case.path, ids), json=_fill(case.json, ids), headers=headers
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c.method} {c.path}")
def test_other_user_gets_404(client, seeded, bob_headers, case):
    response = _call(client, case, bob_headers, seeded)
    assert response.status_code == 404, (
        f"{case.method} {case.path} returned {response.status_code} for a user who does not "
        f"own the data: {response.text[:300]}"
    )
    assert "alice-private-headline" not in response.text


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.owner_status is not None], ids=lambda c: f"{c.method} {c.path}"
)
def test_owner_can_use_the_route(client, seeded, alice_headers, case):
    response = _call(client, case, alice_headers, seeded)
    assert response.status_code == case.owner_status, response.text[:300]


def test_unauthenticated_requests_are_rejected(client, seeded):
    for case in CASES:
        response = _call(client, case, {}, seeded)
        assert response.status_code == 401, f"{case.method} {case.path} -> {response.status_code}"


def test_job_lookup_is_scoped_to_the_user(seeded):
    async def lookup(user_id):
        engine = _new_engine()
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as db:
            profile = await get_job_intelligence(db, user_id, seeded["job_id"])
        await engine.dispose()
        return profile

    assert asyncio.run(lookup(seeded["alice_id"])) is not None
    assert asyncio.run(lookup(seeded["bob_id"])) is None


def test_cached_report_lookups_are_scoped_to_the_user(seeded):
    from app.services.projects.claim_audit_llm import get_cached_claim_audit_report
    from app.services.projects.interview_questions import get_cached_interview_questions

    async def lookup(fn, user_id):
        engine = _new_engine()
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with factory() as db:
            result = await fn(db, user_id, seeded["project_id"])
        await engine.dispose()
        return result

    for fn in (get_cached_claim_audit_report, get_cached_interview_questions):
        assert asyncio.run(lookup(fn, seeded["alice_id"])) is not None
        assert asyncio.run(lookup(fn, seeded["bob_id"])) is None
