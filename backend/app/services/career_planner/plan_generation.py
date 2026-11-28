import logging

from app.core.llm import LLMError, LLMReplyError, Prompt, llm_json
from app.prompts.career_planner.career_planner import CAREER_PLANNER_SYSTEM_PROMPT
from app.schemas.career_planner.career_plan import CareerPlanLLMOutput, DailyPlanItem
from app.schemas.interview.study import LeetcodeTopic
from app.services.evidence.matching import mentions_skill
from app.services.interview.kit_outline import names_topic

logger = logging.getLogger(__name__)

CHUNK_SIZE = 3
RECENT_DAYS_DETAIL_WINDOW = 4
MAX_ATTEMPTS_PER_CHUNK = 3


def _chunk_days(days_available: int, chunk_size: int = CHUNK_SIZE) -> list[list[int]]:
    all_days = list(range(1, days_available + 1))
    return [all_days[i:i + chunk_size] for i in range(0, len(all_days), chunk_size)]


def _focused_topics_so_far(full_plan: list[DailyPlanItem]) -> list[str]:
    return [item.theme for item in full_plan if item.theme]


def _study_for_prompt(study: dict | None) -> dict | None:
    """The study plan without ids and addresses, which the model has no use for."""
    if not study:
        return None
    return {
        "gaps": [
            {
                **{key: gap[key] for key in ("name", "status", "severity", "requirement", "why", "action")},
                "leetcode_topics": [{"topic": t["topic"], "solved": t["solved"]} for t in gap["leetcode"]],
                "interview_questions": [q["text"] for q in gap["questions"]],
            }
            for gap in study["gaps"]
        ],
        "unanswered_questions": [q["text"] for q in study["unanswered"]],
        "weak_answers": [q["text"] for q in study["weak"]],
        "weakest_category": study["weakest_category"],
    }


def _without_links(payload: dict) -> dict:
    days = payload.get("daily_plan")
    if isinstance(days, list):
        for day in days:
            if isinstance(day, dict):
                day.pop("links", None)
    return payload


def _add_links(days: list[DailyPlanItem], study: dict | None) -> None:
    """Gives each day the address of every study-plan LeetCode topic it names in
    a day that speaks of LeetCode. Topic names such as "Stack" or "Design" are
    ordinary words elsewhere.
    """
    topics = {t["topic"]: t for gap in (study or {}).get("gaps", []) for t in gap["leetcode"]}
    for day in days:
        text = " ".join([day.theme, *day.tasks, day.deliverable])
        named = topics.values() if mentions_skill(text, "leetcode") else []
        day.links = [LeetcodeTopic(**t) for t in named if names_topic(text, {t["topic"]})]


async def _call_llm_for_chunk(chunk_context: dict) -> dict[int, DailyPlanItem]:
    reply = await llm_json(
        Prompt(CAREER_PLANNER_SYSTEM_PROMPT, chunk_context), CareerPlanLLMOutput,
        label="career_plan", expect=("daily_plan",), prepare=_without_links, temperature=0.4, max_tokens=1200,
    )
    parsed = reply.value
    out = {}
    for item in parsed.daily_plan:
        item.source = "llm"
        out[item.day] = item
    return out


async def _generate_chunk(
    context: dict, chunk_days: list[int], full_plan: list[DailyPlanItem]
) -> list[DailyPlanItem]:
    """No content-policing here — this only retries on genuine failures
    (bad JSON, missing days, a raised exception). The LLM's creative
    choices about sequencing, task specificity, or which skill_signals
    to act on are never second-guessed or rejected by code.
    """
    logger.debug("Requesting career plan chunk for days %s...", chunk_days)

    resolved: dict[int, DailyPlanItem] = {}
    remaining = list(chunk_days)

    for attempt in range(1, MAX_ATTEMPTS_PER_CHUNK + 1):
        if not remaining:
            break

        recent = full_plan[-RECENT_DAYS_DETAIL_WINDOW:]
        chunk_context = {
            **context,
            "study_plan": _study_for_prompt(context.get("study_plan")),
            "assigned_days": remaining,
            "already_focused_topics": _focused_topics_so_far(full_plan),
            "recent_days_detail": [
                {
                    "day": d.day, "theme": d.theme, "tasks": d.tasks,
                    "deliverable": d.deliverable, "rationale": d.rationale,
                }
                for d in recent
            ],
        }
        try:
            by_day = await _call_llm_for_chunk(chunk_context)
        except Exception as e:
            logger.warning("Days %s attempt %d/%d errored: %s", remaining, attempt, MAX_ATTEMPTS_PER_CHUNK, e)
            # Another attempt only helps when the model answered badly. When
            # the service is unreachable or limited, the client has already
            # retried.
            if isinstance(e, LLMError) and not isinstance(e, LLMReplyError):
                break
            continue

        got = {d: by_day[d] for d in remaining if d in by_day}
        resolved.update(got)
        remaining = [d for d in remaining if d not in resolved]
        if remaining:
            logger.debug("Attempt %d/%d still missing days %s", attempt, MAX_ATTEMPTS_PER_CHUNK, remaining)

    if remaining:
        logger.warning("Days %s using deterministic fallback text after all retries failed", remaining)
        weak_items = _build_weak_items(context)
        covered = set(_focused_topics_so_far(full_plan))  # themes already planned
        for i, day_num in enumerate(remaining):
            skill, rationale, topics = _next_uncovered(weak_items, covered, i)
            covered.add(f"Strengthen {skill}")
            tasks = [f"Review {skill} fundamentals and identify one concrete gap to close today"]
            if topics:
                tasks.append(f"Solve two problems on LeetCode in {topics[0]}")
            resolved[day_num] = DailyPlanItem(
                day=day_num,
                theme=f"Strengthen {skill}",
                tasks=tasks,
                deliverable=f"A short written note on what you learned about {skill}",
                estimated_time="1-2 hours",
                rationale=rationale,
                source="fallback",
            )

    return [resolved[d] for d in chunk_days]


WeakItem = tuple[str, str, list[str]]  # (what to study, why, its LeetCode topics)


def _build_weak_items(context: dict) -> list[WeakItem]:
    """Last-resort safety net only, used when the LLM call fails every
    retry: the target job's gaps, most pressing first, then topic_signals in
    suggested_order, so even a degraded day stays on what the goal needs
    instead of falling back to something generic/irrelevant.
    """
    weak_items: list[WeakItem] = [
        (
            gap["name"], f"{gap['name']} is a {gap['severity']} gap for the target job. {gap['why']}",
            [t["topic"] for t in gap["leetcode"]],
        )
        for gap in (context.get("study_plan") or {}).get("gaps", [])
    ]

    ordered = sorted(context.get("topic_signals", []), key=lambda t: t["suggested_order"])
    for t in ordered:
        reason = "; ".join(t.get("reasons", [])) or f"coverage: {t['coverage']}"
        weak_items.append((t["topic"], f"{t['topic']}: {reason}", []))

    if not weak_items:
        weak_items = [(
            "Foundational review",
            "No curriculum topics resolved for this goal yet — start with fundamentals.",
            [],
        )]

    return weak_items


def _next_uncovered(weak_items: list[WeakItem], covered: set[str], offset: int) -> WeakItem:
    """The most pressing item no day is about yet; once all are, they come round
    again.
    """
    for item in weak_items:
        if f"Strengthen {item[0]}" not in covered:
            return item
    return weak_items[offset % len(weak_items)]


async def generate_career_plan(context: dict) -> tuple[CareerPlanLLMOutput, bool]:
    days_available = context["days_available"]
    chunks = _chunk_days(days_available)

    full_plan: list[DailyPlanItem] = []
    for chunk in chunks:
        full_plan.extend(await _generate_chunk(context, chunk, full_plan))

    _add_links(full_plan, context.get("study_plan"))
    any_degraded = any(item.source == "fallback" for item in full_plan)
    return CareerPlanLLMOutput(daily_plan=full_plan), any_degraded