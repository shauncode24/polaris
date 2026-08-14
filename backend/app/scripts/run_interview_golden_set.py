# backend/app/scripts/run_interview_golden_set.py
"""Hand-run entry point for the Interview Agent golden-set smoke test
(implementation plan §Q, minimal version). Usage:

    python -m app.scripts.run_interview_golden_set --email someone@example.com

Prints a JSON summary to stdout. This talks to a real database and
makes real LLM calls — run it against a dev/staging environment with a
real, populated user, not production data you don't want touched by an
extra read-mostly diagnostic pass.
"""
import argparse
import asyncio
import json

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.facts import User
from app.services.interview.eval_harness import run_golden_set


async def _main(email: str, target_role: str | None, target_company: str | None) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise SystemExit(f"No user found with email {email!r}")

        summary = await run_golden_set(db, user.id, target_role=target_role, target_company=target_company)
        print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Interview Agent golden-set smoke test.")
    parser.add_argument("--email", required=True, help="Email of the user to run the golden set against.")
    parser.add_argument("--target-role", default=None)
    parser.add_argument("--target-company", default=None)
    args = parser.parse_args()

    asyncio.run(_main(args.email, args.target_role, args.target_company))