# backend/app/services/interview/eval_harness.py
"""Minimal, hand-runnable smoke test for the Interview Response Agent
pipeline (implementation plan §Q — "a minimal smoke-test version
should exist before P0 ships"). This is deliberately NOT the full CI
harness (rubric scoring, prompt-version tracking, automated regression
gating) — that stays a Phase 3 item. What this DOES give: a way to
actually run the real pipeline for a real user against the golden set
and get back, per question, whether classification hit its expected
blueprint and whether the final answer's grounding came back clean —
the two axes P0/P1 were explicitly meant to fix.

Run via scripts/run_interview_golden_set.py against a real user_id in
your own dev database. Results are NOT persisted to InterviewResponse
— this is a read-mostly diagnostic pass, not real interview practice
history (though answer generation still hits the LLM and DB reads).
"""
import logging
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.interview.context_builder import build_interview_context
from app.services.interview.golden_set import GOLDEN_QUESTIONS
from app.services.interview.response_generation import (
    InterviewGenerationError,
    classify_blueprint,
    generate_interview_response,
)

logger = logging.getLogger(__name__)


def _grounding_clean(output) -> bool:
    g = output.grounding
    return not g.unverifiable_claims and not g.possible_fabricated_entities


async def run_golden_set(
    db: AsyncSession,
    user_id,
    target_role: str | None = None,
    target_company: str | None = None,
) -> dict:
    """Runs every entry in GOLDEN_QUESTIONS (respecting the g19a/g19b
    continuity pair's shared session) against the real pipeline for
    `user_id`. Returns an aggregate summary plus a per-question result
    list — no hidden pass/fail judgment beyond the two checkable axes
    (blueprint match, grounding cleanliness); a human still has to read
    "answer"/"insufficient_context_reason" for actual answer quality,
    same as the doc's rubric-scoring axis being explicitly out of scope
    for this minimal version.
    """
    session_id = str(uuid4())
    results: list[dict] = []
    blueprint_matches = 0
    grounding_clean_count = 0
    insufficient_count = 0
    error_count = 0

    for entry in GOLDEN_QUESTIONS:
        question = entry["question"]
        expected_blueprint = entry.get("expected_blueprint")
        row: dict = {"id": entry["id"], "question": question, "expected_blueprint": expected_blueprint}

        try:
            blueprint_key = await classify_blueprint(question)
            row["actual_blueprint"] = blueprint_key
            blueprint_match = expected_blueprint is None or blueprint_key == expected_blueprint
            row["blueprint_match"] = blueprint_match
            if blueprint_match:
                blueprint_matches += 1

            context = await build_interview_context(
                db, user_id, question, target_role, target_company,
                session_id=session_id, blueprint_key=blueprint_key,
            )
            output = await generate_interview_response(context, blueprint_key)

            row["insufficient_context"] = output.insufficient_context
            row["insufficient_context_reason"] = output.insufficient_context_reason
            row["stories_used"] = output.stories_used
            row["grounding_clean"] = _grounding_clean(output)
            row["grounding_flags"] = (
                output.grounding.unverifiable_claims + output.grounding.possible_fabricated_entities
            )
            row["answer_short"] = output.answer_short

            if output.insufficient_context:
                insufficient_count += 1
            if row["grounding_clean"]:
                grounding_clean_count += 1

        except InterviewGenerationError as e:
            row["error"] = str(e)
            error_count += 1
        except Exception as e:
            logger.exception("Unexpected error running golden question %s", entry["id"])
            row["error"] = f"unexpected: {e}"
            error_count += 1

        results.append(row)

    total = len(GOLDEN_QUESTIONS)
    return {
        "total_questions": total,
        "blueprint_match_rate": round(blueprint_matches / total, 3) if total else 0.0,
        "grounding_clean_rate": round(grounding_clean_count / total, 3) if total else 0.0,
        "insufficient_context_count": insufficient_count,
        "error_count": error_count,
        "results": results,
    }