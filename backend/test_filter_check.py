import asyncio
from uuid import UUID
from app.core.database import AsyncSessionLocal
from app.models.facts import Project, Experience
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        user_id = "21a7d321-c6cb-4fb5-8c40-cf5ff4492e0d"
        
        # In python, user_id might need to be cast to UUID or kept as string
        # Let's see what is stored in the DB
        proj_result = await db.execute(select(Project.id).where(Project.user_id == user_id))
        user_proj_ids = {p[0] for p in proj_result.all()}
        print("user_proj_ids with string user_id:", user_proj_ids)

        proj_result_uuid = await db.execute(select(Project.id).where(Project.user_id == UUID(user_id)))
        user_proj_ids_uuid = {p[0] for p in proj_result_uuid.all()}
        print("user_proj_ids with UUID user_id:", user_proj_ids_uuid)

        # Let's inspect the first Project's user_id type in SQLAlchemy
        res = await db.execute(select(Project).limit(1))
        p = res.scalar()
        if p:
            print("Project ID:", p.id, "Type of ID:", type(p.id))
            print("Project user_id:", p.user_id, "Type of user_id:", type(p.user_id))

if __name__ == "__main__":
    asyncio.run(main())
