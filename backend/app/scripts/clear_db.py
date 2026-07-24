import asyncio
from sqlalchemy import text
from app.core.database import engine, Base
import app.models  # noqa: F401


async def clear_database():
    async with engine.begin() as conn:
        print("Clearing database...")
        tables = list(Base.metadata.tables.keys())
        if tables:
            tables_str = ", ".join(f'"{table}"' for table in tables)
            query = f"TRUNCATE TABLE {tables_str} RESTART IDENTITY CASCADE;"
            await conn.execute(text(query))
            print(f"Successfully truncated tables: {tables_str}")
        else:
            print("No tables found in Base.metadata.")


if __name__ == "__main__":
    asyncio.run(clear_database())
