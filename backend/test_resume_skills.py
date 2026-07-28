import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.facts import Resume
from app.services.resume.extraction import extract_resume_data

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Resume).order_by(Resume.created_at.desc()).limit(1))
        resume = result.scalar_one_or_none()
        if not resume:
            print("No resumes found.")
            return
        
        print("Extracting resume data with updated prompt...")
        ext = await extract_resume_data(resume.raw_text)
        print("Extracted skills from LLM:", ext.skills)
        print("Extracted experiences:", len(ext.experiences))
        print("Extracted projects:", len(ext.projects))
        print("Extracted education:", len(ext.education))

if __name__ == "__main__":
    asyncio.run(main())
