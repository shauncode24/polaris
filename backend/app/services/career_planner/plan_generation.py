import json

from app.core.llm import client, MODEL
from app.prompts.career_planner import CAREER_PLANNER_SYSTEM_PROMPT
from app.schemas.career_plan import CareerPlanLLMOutput, WeeklyPlanItem

# Smaller chunks = more detailed, reliable output per week (a 4B local
# model produces genuinely good rationale when asked for 2 weeks at a
# time — see the chunk [5,6,7,8] case, which came back fully populated
# and specific). Larger asks push it toward giving up and returning "{}".
CHUNK_SIZE = 2

# How many previously-planned weeks to show the model as "already
# covered" context. Kept small and DELIBERATELY only carries (week,
# focus) — not the full rationale text — because sending the complete,
# ever-growing history every chunk (as the first version of this code
# did) is what caused chunks 3 and 4 to collapse to "{}": by week 9 the
# prompt included 8 previous weeks' full text stacked on top of the
# entire skills_by_confidence list, and the model's context broke down.
PREVIOUS_WEEKS_CONTEXT_WINDOW = 4

MAX_ATTEMPTS_PER_CHUNK = 2


class CareerPlanError(Exception):
    """Raised when a chunk's LLM call fails (after retries) or returns
    something we can't validate for that chunk. Caught internally, per
    chunk — generate_career_plan() never raises this outward, it just
    substitutes a deterministic chunk instead.
    """


def _chunk_weeks(weeks_available: int, chunk_size: int = CHUNK_SIZE) -> list[list[int]]:
    all_weeks = list(range(1, weeks_available + 1))
    return [all_weeks[i:i + chunk_size] for i in range(0, len(all_weeks), chunk_size)]


async def _call_llm_for_chunk(chunk_context: dict, chunk_weeks: list[int]) -> list[WeeklyPlanItem]:
    response = await client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": CAREER_PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(chunk_context)},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=800,
    )
    content = response.choices[0].message.content
    print(f"[TRACING] Raw career plan chunk JSON:\n{content}", flush=True)
    parsed = CareerPlanLLMOutput.model_validate(json.loads(content))

    by_week = {item.week: item for item in parsed.weekly_plan if item.week in chunk_weeks}
    if len(by_week) < len(chunk_weeks):
        raise CareerPlanError(
            f"Chunk {chunk_weeks} only returned {len(by_week)}/{len(chunk_weeks)} weeks "
            f"(raw content: {content!r})"
        )
    return [by_week[w] for w in chunk_weeks]


async def _generate_chunk(chunk_context: dict, chunk_weeks: list[int]) -> list[WeeklyPlanItem]:
    print(f"[TRACING] Requesting career plan chunk for weeks {chunk_weeks}...", flush=True)
    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS_PER_CHUNK + 1):
        try:
            return await _call_llm_for_chunk(chunk_context, chunk_weeks)
        except Exception as e:
            last_error = e
            print(
                f"[TRACING] Chunk {chunk_weeks} attempt {attempt}/{MAX_ATTEMPTS_PER_CHUNK} failed: {e}",
                flush=True,
            )

    raise CareerPlanError(f"Chunk {chunk_weeks} failed after {MAX_ATTEMPTS_PER_CHUNK} attempts: {last_error}")


def _build_weak_items(context: dict) -> list[tuple[str, str]]:
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


def _fallback_chunk(
    weak_items: list[tuple[str, str]], chunk_weeks: list[int], cursor: int
) -> tuple[list[WeeklyPlanItem], int]:
    items = []
    for week_num in chunk_weeks:
        topic, rationale = weak_items[cursor % len(weak_items)]
        items.append(WeeklyPlanItem(week=week_num, focus=[topic], rationale=rationale))
        cursor += 1
    return items, cursor


async def generate_career_plan(context: dict) -> tuple[CareerPlanLLMOutput, bool]:
    """Builds the full weekly plan across several small LLM calls
    (CHUNK_SIZE weeks each). Every chunk receives the FULL skill/evidence
    context — nothing trimmed there — but the "already planned" history
    passed back to the model is deliberately kept small and flat (only
    the last PREVIOUS_WEEKS_CONTEXT_WINDOW weeks, focus only) so prompt
    size stays roughly constant across chunks instead of growing every
    call, which is what caused later chunks to collapse before.
    """
    weeks_available = context["weeks_available"]
    chunks = _chunk_weeks(weeks_available)
    weak_items = _build_weak_items(context)

    full_plan: list[WeeklyPlanItem] = []
    fallback_cursor = 0
    any_degraded = False

    for chunk in chunks:
        recent_weeks = full_plan[-PREVIOUS_WEEKS_CONTEXT_WINDOW:]
        chunk_context = {
            **context,
            "chunk_weeks": chunk,
            "previously_planned_weeks": [
                {"week": w.week, "focus": w.focus} for w in recent_weeks
            ],
        }
        try:
            chunk_items = await _generate_chunk(chunk_context, chunk)
        except CareerPlanError as e:
            print(f"[TRACING] Chunk {chunk} degraded, using deterministic fallback: {e}", flush=True)
            chunk_items, fallback_cursor = _fallback_chunk(weak_items, chunk, fallback_cursor)
            any_degraded = True
        full_plan.extend(chunk_items)

    milestone_check_ins = (
        [f"End of Week {w}" for w in range(4, weeks_available + 1, 4)]
        or [f"End of Week {weeks_available}"]
    )

    return CareerPlanLLMOutput(weekly_plan=full_plan, milestone_check_ins=milestone_check_ins), any_degraded