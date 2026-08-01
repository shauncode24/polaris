import json
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.inference import LeetcodePortfolioReview
from app.prompts.leetcode_review import LEETCODE_REVIEW_SYSTEM_PROMPT
from app.schemas.leetcode_review import LeetcodePortfolioReviewLLMOutput, LeetcodePortfolioReviewReport
from app.services.leetcode.leetcode_knowledge import build_leetcode_knowledge_object
from app.services.leetcode.leetcode_taxonomy import CANONICAL_TOPICS
from app.services.leetcode.company_readiness import COMPANY_TOPIC_WEIGHTS

logger = logging.getLogger(__name__)


# Common real companies the model might reach for out of habit even
# though they're outside our hand-seeded COMPANY_TOPIC_WEIGHTS set —
# not exhaustive, just enough to catch the likely hallucination cases.
# Mirrors the defensive-guard pattern github_reviewer.py already applies
# to its role_fit field, applied here to prose instead of a structured field.
_COMMONLY_HALLUCINATED_COMPANIES = {
    "Apple", "Netflix", "Uber", "Airbnb", "Stripe", "Bloomberg", "Goldman Sachs", "Facebook",
}


def _flag_ungrounded_company_mentions(text: str) -> list[str]:
    """Free text has no safe post-hoc filter the way an enum field does
    (you can't silently strip a company name out of a sentence without
    mangling it), so this only LOGS — it gives visibility into whether
    the model is naming companies outside the real, given
    COMPANY_TOPIC_WEIGHTS set, without mutating what the user sees.
    """
    if not text:
        return []
    known = set(COMPANY_TOPIC_WEIGHTS.keys())
    return [c for c in _COMMONLY_HALLUCINATED_COMPANIES if c in text and c not in known]


def _fallback_report(knowledge: dict) -> LeetcodePortfolioReviewLLMOutput:
    """Deterministic, template-built fallback for when the LLM call
    fails or times out. Previously this only reflected blind spots,
    discarding the quadrant/company-readiness/resume-claims/plan-adherence
    signal the primary path has already assembled — every real fact used
    below was already computed deterministically before the LLM was even
    called, so a degraded response should still be able to cite it.
    """
    blind_spots = knowledge.get("blind_spots", {})
    missing_fundamentals = blind_spots.get("missing_fundamentals", [])

    quadrant = knowledge.get("engineering_quadrant")
    readiness = knowledge.get("company_readiness", [])
    resume_claims = knowledge.get("resume_claims", {})
    plan_adherence = knowledge.get("plan_adherence", [])

    coach_parts = []
    if quadrant:
        coach_parts.append(
            f"Your current placement is '{quadrant['quadrant_label']}' "
            f"(LeetCode score {quadrant['leetcode_score']}/100, GitHub score {quadrant['github_score']}/100)."
        )
    if readiness:
        strongest, weakest = readiness[0], readiness[-1]
        coach_parts.append(
            f"You're closest to ready for {strongest['company']} ({strongest['readiness_pct']}%) "
            f"and furthest from {weakest['company']} ({weakest['readiness_pct']}%), "
            f"with weak spots in {', '.join(weakest['weak_topics'][:2]) or 'multiple areas'}."
        )
    if resume_claims.get("mismatches"):
        coach_parts.append("Your resume makes DSA-related claims your current LeetCode evidence doesn't yet back up.")
    not_followed = [a for a in plan_adherence if a.get("status") == "not_yet_followed"]
    if not_followed:
        coach_parts.append(
            f"A previous recommendation to focus on {not_followed[0]['topic']} hasn't been acted on yet."
        )
    coach_parts.append(
        "This reads solved-problem counts and recency as a proxy for practice depth, not a "
        "guarantee of live interview performance."
    )

    focus = missing_fundamentals[:2] if missing_fundamentals else (
        [readiness[-1]["weak_topics"][0]] if readiness and readiness[-1]["weak_topics"] else ["Trees", "Graphs"]
    )
    actions = [f"Solve 5 Medium problems in {topic}." for topic in focus]
    if resume_claims.get("opportunities"):
        actions.append("Add your real solved-problem evidence to your resume — it's currently unmentioned there.")

    return LeetcodePortfolioReviewLLMOutput(
        interview_coach=" ".join(coach_parts),
        learning_strategy=(
            "Prioritize fundamental topics where you have no solved problems yet, and revisit any "
            "topic flagged stale before it decays further. Narrative coaching is temporarily unavailable "
            "— this is a deterministic summary of your real, computed evidence."
        ),
        target_focus_topics=focus,
        roadmap_actions=actions,
    )


async def generate_leetcode_portfolio_review(db: AsyncSession, user_id) -> LeetcodePortfolioReviewReport:
    """Invokes the LLM to analyze the user's LeetCode performance and compile
    the dynamic Interview Coach feedback and Learning Strategy roadmap.
    """
    knowledge = await build_leetcode_knowledge_object(db, user_id)
    if knowledge is None:
        raise ValueError("No LeetCode sync history found. Please run a sync first.")

    degraded = False
    try:
        logger.info("Requesting LeetCode portfolio review from LLM...")
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": LEETCODE_REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(knowledge)},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
            max_tokens=2000,
        )
        content = response.choices[0].message.content
        logger.debug("Raw LeetCode portfolio review JSON: %s", content)
        llm_output = LeetcodePortfolioReviewLLMOutput.model_validate(json.loads(content))

        ungrounded = (
            _flag_ungrounded_company_mentions(llm_output.interview_coach)
            + _flag_ungrounded_company_mentions(llm_output.learning_strategy)
        )
        if ungrounded:
            logger.warning(
                "LeetCode portfolio review mentioned company name(s) outside COMPANY_TOPIC_WEIGHTS: %s",
                sorted(set(ungrounded)),
            )
    except Exception as e:
        logger.warning("LeetCode portfolio review degraded, using fallback: %s", e)
        llm_output = _fallback_report(knowledge)
        degraded = True

    # Validate target focus topics against the exact set of canonical topics to avoid LLM hallucination
    allowed_topics = set(CANONICAL_TOPICS.keys())
    validated_topics = []
    for topic in llm_output.target_focus_topics:
        if topic in allowed_topics:
            validated_topics.append(topic)
        else:
            logger.warning("Dropped non-canonical target focus topic: %s", topic)
    llm_output.target_focus_topics = validated_topics

    report = LeetcodePortfolioReviewReport(
        **llm_output.model_dump(),
        generated_at=datetime.now(timezone.utc).isoformat(),
        analysis_degraded=degraded,
    )

    review_row = LeetcodePortfolioReview(
        user_id=user_id,
        review_json=report.model_dump(mode="json"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(review_row)
    await db.flush()
    await db.commit()

    return report
