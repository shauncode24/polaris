import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import chat_completion, MODEL
from app.models.inference import LeetcodePortfolioReview
from app.prompts.leetcode_review import LEETCODE_REVIEW_SYSTEM_PROMPT
from app.schemas.leetcode_review import LeetcodePortfolioReviewLLMOutput, LeetcodePortfolioReviewReport
from app.services.leetcode.leetcode_knowledge import build_leetcode_knowledge_object


def _fallback_report(knowledge: dict) -> LeetcodePortfolioReviewLLMOutput:
    """Generate a clean, static fallback report if the Groq/LLM call fails or times out."""
    blind_spots = knowledge.get("blind_spots", {})
    missing_fundamentals = blind_spots.get("missing_fundamentals", [])
    
    focus = missing_fundamentals[:2] if missing_fundamentals else ["Trees", "Graphs"]
    actions = [f"Solve 5 Medium problems in {topic}." for topic in focus]
    
    return LeetcodePortfolioReviewLLMOutput(
        interview_coach=(
            "Your profile indicates a strong foundation, but you would benefit from structuring "
            "your practice around core data structures and algorithms expected in technical interviews."
        ),
        learning_strategy=(
            "Prioritize fundamental topics where you have no solved problems yet. Transition "
            "away from Easy-difficulty tasks and build stamina on Medium-difficulty interview questions."
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
        print("[TRACING] Requesting LeetCode portfolio review from LLM...", flush=True)
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": LEETCODE_REVIEW_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(knowledge)},
            ],
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw LeetCode portfolio review JSON:\n{content}", flush=True)
        llm_output = LeetcodePortfolioReviewLLMOutput.model_validate(json.loads(content))
    except Exception as e:
        print(f"[TRACING] LeetCode portfolio review degraded, using fallback: {e}", flush=True)
        llm_output = _fallback_report(knowledge)
        degraded = True

    # Validate target focus topics against a set of allowed values to avoid LLM hallucination
    allowed_topics = {
        "Arrays & Hashing", "Strings", "Sliding Window", "Stack", "Queue",
        "Linked List", "Trees", "Graphs", "Binary Search", "Sorting", "Recursion",
        "Math", "Heap", "Trie", "Dynamic Programming", "Greedy", "Backtracking",
        "Bit Manipulation", "Intervals", "Design"
    }
    validated_topics = []
    for topic in llm_output.target_focus_topics:
        topic_lower = topic.lower()
        if any(allowed.lower() in topic_lower or topic_lower in allowed.lower() for allowed in allowed_topics):
            validated_topics.append(topic)
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
