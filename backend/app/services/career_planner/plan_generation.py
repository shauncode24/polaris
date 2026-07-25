import json

from app.core.llm import client, MODEL
from app.prompts.career_planner import CAREER_PLANNER_SYSTEM_PROMPT
from app.schemas.career_plan import CareerPlanLLMOutput, DailyPlanItem

CHUNK_SIZE = 3
RECENT_DAYS_DETAIL_WINDOW = 4
MAX_ATTEMPTS_PER_CHUNK = 3


def _chunk_days(days_available: int, chunk_size: int = CHUNK_SIZE) -> list[list[int]]:
    all_days = list(range(1, days_available + 1))
    return [all_days[i:i + chunk_size] for i in range(0, len(all_days), chunk_size)]


def _focused_topics_so_far(full_plan: list[DailyPlanItem]) -> list[str]:
    return [item.theme for item in full_plan if item.theme]


async def _call_llm_for_chunk(chunk_context: dict) -> dict[int, DailyPlanItem]:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": CAREER_PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(chunk_context)},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
        max_tokens=1200,
    )
    content = response.choices[0].message.content
    print(f"[TRACING] Raw career plan chunk JSON:\n{content}", flush=True)
    parsed = CareerPlanLLMOutput.model_validate(json.loads(content))
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
    print(f"[TRACING] Requesting career plan chunk for days {chunk_days}...", flush=True)

    resolved: dict[int, DailyPlanItem] = {}
    remaining = list(chunk_days)

    for attempt in range(1, MAX_ATTEMPTS_PER_CHUNK + 1):
        if not remaining:
            break

        recent = full_plan[-RECENT_DAYS_DETAIL_WINDOW:]
        chunk_context = {
            **context,
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
            print(f"[TRACING] Days {remaining} attempt {attempt}/{MAX_ATTEMPTS_PER_CHUNK} errored: {e}", flush=True)
            continue

        got = {d: by_day[d] for d in remaining if d in by_day}
        resolved.update(got)
        remaining = [d for d in remaining if d not in resolved]
        if remaining:
            print(f"[TRACING] Attempt {attempt}/{MAX_ATTEMPTS_PER_CHUNK} still missing days {remaining}", flush=True)

    if remaining:
        print(f"[TRACING] Days {remaining} using deterministic fallback text after all retries failed", flush=True)
        weak_items = _build_weak_items(context)
        covered = set(_focused_topics_so_far(full_plan))
        for i, day_num in enumerate(remaining):
            skill, rationale = _next_uncovered(weak_items, covered, i)
            covered.add(skill)
            resolved[day_num] = DailyPlanItem(
                day=day_num,
                theme=f"Strengthen {skill}",
                tasks=[f"Review {skill} fundamentals and identify one concrete gap to close today"],
                deliverable=f"A short written note on what you learned about {skill}",
                estimated_time="1-2 hours",
                rationale=rationale,
                source="fallback",
            )

    return [resolved[d] for d in chunk_days]


def _build_weak_items(context: dict) -> list[tuple[str, str]]:
    """Last-resort safety net only, used when the LLM call fails every
    retry. Walks topic_signals in suggested_order (lowest coverage
    first isn't even necessary here — this is purely a safety net, not
    a quality bar) so even a degraded day stays inside the goal's
    curriculum instead of falling back to something generic/irrelevant.
    """
    weak_items: list[tuple[str, str]] = []

    ordered = sorted(context.get("topic_signals", []), key=lambda t: t["suggested_order"])
    for t in ordered:
        reason = "; ".join(t.get("reasons", [])) or f"coverage: {t['coverage']}"
        weak_items.append((t["topic"], f"{t['topic']}: {reason}"))

    if not weak_items:
        weak_items = [(
            "Foundational review",
            "No curriculum topics resolved for this goal yet — start with fundamentals.",
        )]

    return weak_items

def _next_uncovered(weak_items: list[tuple[str, str]], covered: set[str], offset: int) -> tuple[str, str]:
    n = len(weak_items)
    for i in range(n):
        skill, rationale = weak_items[(offset + i) % n]
        if skill not in covered:
            return skill, rationale
    return weak_items[offset % n]


async def generate_career_plan(context: dict) -> tuple[CareerPlanLLMOutput, bool]:
    days_available = context["days_available"]
    chunks = _chunk_days(days_available)

    full_plan: list[DailyPlanItem] = []
    for chunk in chunks:
        full_plan.extend(await _generate_chunk(context, chunk, full_plan))

    any_degraded = any(item.source == "fallback" for item in full_plan)
    return CareerPlanLLMOutput(daily_plan=full_plan), any_degraded