import asyncio
from app.core.database import AsyncSessionLocal
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        skill_res = await db.execute(select(Skill).where(Skill.canonical_name == "vector_search"))
        skill = skill_res.scalar()
        if not skill:
            print("Skill 'vector_search' not found!")
            return
            
        print(f"Skill: {skill.canonical_name} (ID: {skill.id})")
        ev_res = await db.execute(select(SkillEvidence).where(SkillEvidence.skill_id == skill.id))
        ev_rows = ev_res.scalars().all()
        print(f"Total evidence rows: {len(ev_rows)}")
        for r in ev_rows:
            print(f"ID: {r.id}, source_type: {repr(r.source_type)}, source_id: {r.source_id}, weight: {r.weight}")

if __name__ == "__main__":
    asyncio.run(main())
