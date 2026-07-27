import asyncio
from uuid import UUID
from app.core.database import AsyncSessionLocal
from app.models.facts import Project, Experience
from app.models.inference import SkillEvidence
from app.models.structure import Skill
from app.services.interview.context_builder import _get_all_skills_with_evidence
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        user_id = "21a7d321-c6cb-4fb5-8c40-cf5ff4492e0d"
        user_id_uuid = UUID(user_id)
        
        # Run original code's database queries
        proj_result = await db.execute(select(Project.id).where(Project.user_id == user_id_uuid))
        user_proj_ids = {p[0] for p in proj_result.all()}
        print("user_proj_ids set:", user_proj_ids)

        exp_result = await db.execute(select(Experience.id).where(Experience.user_id == user_id_uuid))
        user_exp_ids = {e[0] for e in exp_result.all()}
        print("user_exp_ids set:", user_exp_ids)

        # Query vector_search skill
        skill_res = await db.execute(select(Skill).where(Skill.canonical_name == "vector_search"))
        skill = skill_res.scalar()
        print(f"Checking skill '{skill.canonical_name}'...")

        evidence_result = await db.execute(select(SkillEvidence).where(SkillEvidence.skill_id == skill.id))
        evidence_rows = list(evidence_result.scalars().all())
        print(f"Total evidence rows for '{skill.canonical_name}': {len(evidence_rows)}")

        filtered_rows = []
        for e in evidence_rows:
            print(f"Examining evidence: source_type={repr(e.source_type)}, source_id={e.source_id}")
            if e.source_type == "project":
                is_in = e.source_id in user_proj_ids
                print(f"  source_type is project. Is source_id in user_proj_ids? {is_in}")
                if is_in:
                    filtered_rows.append(e)
            elif e.source_type == "experience":
                is_in = e.source_id in user_exp_ids
                print(f"  source_type is experience. Is source_id in user_exp_ids? {is_in}")
                if is_in:
                    filtered_rows.append(e)
            else:
                print(f"  source_type is other. Appending.")
                filtered_rows.append(e)

        print("Filtered rows count:", len(filtered_rows))

if __name__ == "__main__":
    asyncio.run(main())
