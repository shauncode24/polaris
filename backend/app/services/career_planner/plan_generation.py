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
    """Every focus item used anywhere in the plan so far — passed to the
    model as ADVISORY context only. Nothing here forces the model's next
    choice; it's information to reason with, same as any other fact in
    the context (confidence scores, evidence). The model decides.
    """
    seen: list[str] = []
    for item in full_plan:
        for f in item.focus:
            if f not in seen:
                seen.append(f)
    return seen


async def _call_llm_for_chunk(chunk_context: dict) -> dict[int, DailyPlanItem]:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": CAREER_PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(chunk_context)},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=700,
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
    """Retries only ask for the days still missing, and any day the model
    already got right on an earlier attempt is kept — not discarded just
    because a sibling day in the same chunk failed.
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
                {"day": d.day, "focus": d.focus, "rationale": d.rationale} for d in recent
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
            topic, rationale = _next_uncovered(weak_items, covered, i)
            covered.add(topic)
            resolved[day_num] = DailyPlanItem(day=day_num, focus=[topic], rationale=rationale, source="fallback")

    return [resolved[d] for d in chunk_days]


def _build_weak_items(context: dict) -> list[tuple[str, str]]:
    """Used ONLY as the last-resort safety net if the LLM genuinely fails
    every retry for a day — never the primary path. The primary path is
    always the LLM reasoning over the real context above.
    """
    weak_items: list[tuple[str, str]] = []

    blind_spots = context.get("leetcode_blind_spots", {})
    for bs_type, label in (
        ("missing_fundamentals", "fundamental DSA gap"),
        ("advanced_topics", "advanced DSA gap"),
    ):
        for topic in blind_spots.get(bs_type, []):
            weak_items.append((topic, f"{topic} has 0 solved LeetCode problems — a {label}."))

    for s in context.get("skills_by_confidence", []):
        weak_items.append((
            s["skill"],
            f"{s['skill'].title()} confidence is {s['confidence']:.2f} — low verified evidence.",
        ))

    if not weak_items:
        weak_items = [(
            "Foundational review",
            "No skill or LeetCode evidence found yet — start building verifiable evidence.",
        )]

    return weak_items


def _next_uncovered(weak_items: list[tuple[str, str]], covered: set[str], offset: int) -> tuple[str, str]:
    n = len(weak_items)
    for i in range(n):
        topic, rationale = weak_items[(offset + i) % n]
        if topic not in covered:
            return topic, rationale
    return weak_items[offset % n]


async def generate_career_plan(context: dict) -> tuple[CareerPlanLLMOutput, bool]:
    """Builds the full day-by-day plan across several small LLM calls.
    The LLM decides every day's topic/focus/rationale itself — nothing
    is pre-assigned in code. Chunking exists purely to keep each call's
    generation burden small enough for a local model to handle reliably;
    it does not constrain what the model is allowed to choose.
    """
    days_available = context["days_available"]
    chunks = _chunk_days(days_available)

    full_plan: list[DailyPlanItem] = []
    for chunk in chunks:
        full_plan.extend(await _generate_chunk(context, chunk, full_plan))

    any_degraded = any(item.source == "fallback" for item in full_plan)

    check_ins = ["Final review day before the interview/deadline"]
    if days_available >= 5:
        check_ins = [f"Day {d} check-in" for d in range(3, days_available + 1, 3)] + [
            "Final review day before the interview/deadline"
        ]

    return CareerPlanLLMOutput(daily_plan=full_plan, check_ins=check_ins), any_degraded