"""Fixtures for database-backed API tests.

The schema is rebuilt from the Alembic migrations once per test session
(which also proves the migrations build a working schema from empty), then
two users are seeded: `alice`, who owns data, and `bob`, who owns nothing.
"""
import asyncio
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.deps import get_current_user  # noqa: E402,F401
from app.core.database import get_db  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.core.settings import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models.background import BackgroundJob  # noqa: E402
from app.models.facts import Education, Experience, Project, Resume, User  # noqa: E402
from app.models.goals import Goal  # noqa: E402
from app.models.inference import (  # noqa: E402
    EngineeringIdentity,
    InterviewResponse,
    ProjectClaimAuditReview,
    ProjectInterviewQuestionsReview,
    ResumeTailoringReview,
)
from app.models.job_intelligence import GapAnalysisResultRow, JobIntelligenceProfileRow  # noqa: E402
from app.services.background import jobs as background_jobs  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _new_engine():
    # NullPool: every checkout opens a fresh connection, so connections are
    # never reused across the separate event loops the test client creates.
    return create_async_engine(settings.database_url, connect_args=settings.connect_args, poolclass=NullPool)


async def _reset_schema() -> None:
    engine = _new_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    await engine.dispose()


async def _seed() -> dict:
    now = datetime.now(timezone.utc)
    engine = _new_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        alice = User(name="Alice", email="alice@example.test", auth_provider="local",
                     target_roles=[], target_companies=[])
        bob = User(name="Bob", email="bob@example.test", auth_provider="local",
                   target_roles=[], target_companies=[])
        db.add_all([alice, bob])
        await db.flush()

        resume = Resume(user_id=alice.id, raw_text="Alice resume")
        project = Project(user_id=alice.id, name="Alice Project", stack=["python"], description="d")
        job = JobIntelligenceProfileRow(
            user_id=alice.id, source_text_hash="hash-alice", created_at=now,
            profile_json={"role": "Backend Engineer", "company": "Acme"},
        )
        experience = Experience(
            user_id=alice.id, resume_id=resume.id, role="Engineer", company="Acme",
            stack=["python"], bullets=["Built things"],
        )
        education = Education(user_id=alice.id, resume_id=resume.id, institution="State University", degree="BSc")
        db.add_all([resume, project, job, experience, education])
        await db.flush()

        gap = GapAnalysisResultRow(
            user_id=alice.id, job_intelligence_id=job.id, created_at=now,
            report_json={"have": [], "partial": [], "missing": []},
            category_breakdown_json={"items": []},
            overall_match_json={"percentage": 50, "label": "Moderate"},
            narrative_json={},
        )
        goal = Goal(user_id=alice.id, job_intelligence_id=job.id, title="Alice goal", status_pct=0.0)
        session_id = uuid.uuid4()
        response = InterviewResponse(
            user_id=alice.id, question="Tell me about yourself", question_type="behavioral",
            response_json={}, session_id=session_id, created_at=now,
        )
        identity = EngineeringIdentity(
            user_id=alice.id, facts_json={}, narrative_json={}, created_at=now,
        )
        background_job = BackgroundJob(
            user_id=alice.id, kind="resume_review", dedupe_key="resume_review:seeded", status="succeeded",
            result_json={"summary": "alice-private-headline"}, created_at=now, heartbeat_at=now, finished_at=now,
        )
        db.add_all([gap, goal, response, identity, background_job])
        await db.flush()

        db.add_all([
            ProjectClaimAuditReview(
                user_id=alice.id, project_id=project.id,
                report_json={
                    "facts": {"project_name": "Alice Project", "has_repo_match": True},
                    "narrative": {"headline": "alice-private-headline"},
                },
            ),
            ProjectInterviewQuestionsReview(
                user_id=alice.id, project_id=project.id,
                report_json={"project_name": "Alice Project", "questions": []},
            ),
            ResumeTailoringReview(
                user_id=alice.id, resume_id=resume.id, job_intelligence_id=job.id,
                report_json={"role": "Backend Engineer", "llm": {}},
            ),
        ])
        await db.commit()

        ids = {
            "alice_id": alice.id, "bob_id": bob.id,
            "project_id": project.id, "job_id": job.id, "goal_id": goal.id,
            "experience_id": experience.id, "education_id": education.id,
            "session_id": session_id, "response_id": response.id, "identity_id": identity.id,
            "background_job_id": background_job.id,
        }
    await engine.dispose()
    return ids


@pytest.fixture(scope="session")
def seeded() -> dict:
    asyncio.run(_reset_schema())
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, "head")
    return asyncio.run(_seed())


class WaitingClient(TestClient):
    """Waits for background jobs as the frontend does: a 202 is replaced by
    the finished job's status and body. `start` returns the 202 itself.
    """

    def request(self, method, url, **kwargs):
        response = super().request(method, url, **kwargs)
        if response.status_code != 202:
            return response
        job_id = response.json()["job_id"]
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            job = super().request("GET", f"/background-jobs/{job_id}", headers=kwargs.get("headers")).json()
            if job["status"] == "succeeded":
                return httpx.Response(200, json=job["result"])
            if job["status"] == "failed":
                return httpx.Response(job["error_status"], json={"detail": job["error_detail"]})
            time.sleep(0.02)
        raise AssertionError(f"background job {job_id} did not finish")

    def start(self, method, url, **kwargs):
        return super().request(method, url, **kwargs)


@pytest.fixture(scope="session")
def client(seeded):
    engine = _new_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    real_factory, background_jobs.session_factory = background_jobs.session_factory, factory
    with WaitingClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    background_jobs.session_factory = real_factory


def _auth(user_id) -> dict:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


@pytest.fixture(scope="session")
def alice_headers(seeded) -> dict:
    return _auth(seeded["alice_id"])


@pytest.fixture(scope="session")
def bob_headers(seeded) -> dict:
    return _auth(seeded["bob_id"])
