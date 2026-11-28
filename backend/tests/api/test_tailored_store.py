"""Tailored resumes are stored as numbered versions per job, visible only to
their owner. Real database.
"""
import asyncio
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.tailored_resume import TailoredResume
from app.schemas.resume.tailored import TailoredResumeDocument
from app.services.resume.tailored_store import document_of, get_version, save_new_version
from tests.api.conftest import _new_engine
from tests.api.test_evidence import auth, run
from tests.api.test_job_library import add_job, new_user


def resume(name="Sam Rivera") -> TailoredResumeDocument:
    return TailoredResumeDocument(
        header={"full_name": name},
        projects=[{
            "name": "Ledger", "sources": [{"kind": "project", "id": str(uuid.uuid4())}],
            "bullets": [{"original": "Built a ledger.", "sources": [{"kind": "project", "id": str(uuid.uuid4()), "bullet": 0}]}],
        }],
    )


def save(user, job_id, document):
    async def go(db):
        return await save_new_version(db, user.id, uuid.UUID(job_id), document)
    return run(go)


def load(user, job_id, version=None):
    async def go(db):
        return await get_version(db, user.id, uuid.UUID(job_id), version)
    return run(go)


def test_each_save_is_the_next_version_of_that_jobs_resume(seeded):
    user = new_user()
    backend, data = add_job(user, "Backend Engineer"), add_job(user, "Data Engineer")
    first = resume("First")

    saved = [save(user, backend, first), save(user, backend, resume("Second")), save(user, data, resume("Other"))]

    assert [(r.version, r.status) for r in saved] == [(1, "draft"), (2, "draft"), (1, "draft")]
    assert document_of(load(user, backend)).header.full_name == "Second"
    assert document_of(load(user, backend, 1)) == first
    assert load(user, backend, 3) is None
    assert load(user, data).version == 1


def test_another_users_job_and_resume_are_out_of_reach(seeded):
    owner, other = new_user(), new_user()
    job = add_job(owner, "Backend Engineer")
    save(owner, job, resume())

    assert save(other, job, resume("Intruder")) is None
    assert load(other, job) is None
    assert load(owner, job).version == 1


def test_saves_made_at_the_same_moment_get_different_versions(seeded):
    user = new_user()
    job = uuid.UUID(add_job(user, "Backend Engineer"))

    async def all_at_once():
        engine = _new_engine()
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        async def one():
            async with factory() as db:
                return (await save_new_version(db, user.id, job, resume())).version
        try:
            return await asyncio.gather(*(one() for _ in range(5)))
        finally:
            await engine.dispose()

    assert sorted(asyncio.run(all_at_once())) == [1, 2, 3, 4, 5]


def test_deleting_a_job_deletes_its_resumes_and_no_others(client, seeded):
    user = new_user()
    doomed, kept = add_job(user, "Backend Engineer"), add_job(user, "Data Engineer")
    save(user, doomed, resume())
    save(user, kept, resume())

    response = client.delete(f"/job-intelligence/{doomed}", headers=auth(user.id))

    assert response.status_code == 200, response.text[:300]

    async def remaining(db):
        result = await db.execute(select(TailoredResume.job_intelligence_id).where(TailoredResume.user_id == user.id))
        return [str(i) for i in result.scalars().all()]
    assert run(remaining) == [kept]
