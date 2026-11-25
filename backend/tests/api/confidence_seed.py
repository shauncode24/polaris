"""A small, fixed evidence scenario for pinning confidence behaviour."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.facts import Project, User
from app.models.inference import SkillEvidence
from app.models.structure import Skill


async def seed_dana(engine) -> dict:
    """Dana has three skills:
      python — project evidence (fresh) + leetcode (fresh): two source types
      docker — one project mention from ~400 days ago
      go     — a single fresh leetcode tag
    plus a skill with no evidence at all (rust), which must never appear.
    """
    now = datetime.now(timezone.utc)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as db:
        dana = User(name="Dana", email="dana@example.test", auth_provider="local",
                    target_roles=[], target_companies=[])
        db.add(dana)
        await db.flush()
        project = Project(user_id=dana.id, name="Dana Project", stack=["python"], description="d")
        python = Skill(name="python", canonical_name="python", category="language")
        docker = Skill(name="docker", canonical_name="docker", category="devops")
        go = Skill(name="go", canonical_name="go", category="language")
        rust = Skill(name="rust", canonical_name="rust", category="language")
        db.add_all([project, python, docker, go, rust])
        await db.flush()
        db.add_all([
            SkillEvidence(user_id=dana.id, skill_id=python.id, source_type="project",
                          source_id=project.id, weight=0.35, created_at=now - timedelta(days=10)),
            SkillEvidence(user_id=dana.id, skill_id=python.id, source_type="leetcode_tag",
                          source_id=None, weight=0.10, created_at=now - timedelta(days=10)),
            SkillEvidence(user_id=dana.id, skill_id=docker.id, source_type="project",
                          source_id=project.id, weight=0.35, created_at=now - timedelta(days=400)),
            SkillEvidence(user_id=dana.id, skill_id=go.id, source_type="leetcode_tag",
                          source_id=None, weight=0.10, created_at=now - timedelta(days=10)),
        ])
        await db.commit()
        return {"user_id": dana.id, "python_id": python.id, "docker_id": docker.id,
                "go_id": go.id, "rust_id": rust.id}
