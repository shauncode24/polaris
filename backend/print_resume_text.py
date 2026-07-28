import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.facts import Resume

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Resume).order_by(Resume.created_at.desc()).limit(1))
        resume = result.scalar_one_or_none()
        if not resume:
            print("No resumes found.")
            return
        print("--- RESUME RAW TEXT ---")
        print(resume.raw_text)
        print("-----------------------")

if __name__ == "__main__":
    asyncio.run(main())
