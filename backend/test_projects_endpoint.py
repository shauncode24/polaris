import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.facts import Project
from app.services.projects.overview import build_projects_overview

async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Project.user_id).distinct().limit(1))
        row = result.fetchone()
        if not row:
            print("No project users found.")
            return
        
        user_id = row[0]
        print(f"Building projects overview for user: {user_id}...")
        overview = await build_projects_overview(db, user_id)
        print("Overview built successfully!")
        print("Stats:", overview.stats)
        print("Number of projects:", len(overview.projects))

if __name__ == "__main__":
    asyncio.run(main())
