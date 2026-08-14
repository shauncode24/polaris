# backend/app/services/interview/response_generation.py
"""Phase 1 pipeline (implementation plan §F/§G/§H/§I/§N/§R/§S) plus
this pass's §A addition:

  §A — classify_blueprint() now also captures the classifier's own
       confidence and the competency tags it believes the question
       tests, logs both, and tracks a running fallback-rate metric
       (how often classification silently defaulted to
       "behavioral_default" because the call itself failed, as opposed
       to genuinely picking that key as the best fit). This was
       previously invisible — a rising fallback rate meant more and
       more real questions getting generic handling with no signal
       anywhere that it was happening.

classify_blueprint() itself still returns a plain blueprint_key string
(everything downstream — context_builder's ranking, the plan prompt's
blueprint_library lookup — only ever needed the key), so this is
additive, not a breaking signature change.
"""
import hashlib
import json
import logging
import os
from uuid import uuid4

from app.core.llm import chat_completion, MODEL as DEFAULT_MODEL

logger = logging.getLogger(__name__)

from app.prompts.interview.interview_response import (
    ANSWER_PLAN_SYSTEM_PROMPT,
    BLUEPRINT_CLASSIFICATION_PROMPT,
    PROSE_GENERATION_SYSTEM_PROMPT,
)
from app.schemas.interview.interview_response import (
    AnswerPlan,
    BlueprintClassification,
    GroundingReport,
    InterviewLLMOutput,
    ProseOutput,
)
from app.services.interview import grounding
from app.services.interview.blueprints import BLUEPRINTS

DEFAULT_BLUEPRINT = "behavioral_default"
_VALID_COMPETENCIES = frozenset({
    "leadership", "teamwork", "conflict_resolution", "ownership",
    "problem_solving", "technical_depth", "failure_recovery", "mentorship",
})
_VALID_CLASSIFICATION_CONFIDENCE = frozenset({"low", "medium", "high"})

INTERVIEW_MODEL = os.environ.get("INTERVIEW_MODEL", "llama-3.3-70b-versatile")
INTERVIEW_TIMEOUT_SECONDS = float(os.environ.get("INTERVIEW_TIMEOUT_SECONDS", "45"))
CLASSIFY_TIMEOUT_SECONDS = float(os.environ.get("INTERVIEW_CLASSIFY_TIMEOUT_SECONDS", "15"))

MAX_CLASSIFY_TOKENS = 250
MAX_PLAN_TOKENS = 1400
MAX_PROSE_TOKENS = 700

MAX_PLAN_ATTEMPTS = 3
MAX_PROSE_ATTEMPTS = 2


def _compute_prompt_version() -> str:
    """Stable, content-addressed version tag for the two prompt strings
    in use right now. Format: '<8-char plan hash>/<8-char prose hash>'.
    Derived from the actual bytes of the prompts, so it changes
    automatically whenever a prompt changes — no manual versioning
    needed. Computed once per call rather than at module import so it
    always reflects whatever the prompts read at call time (useful when
    prompts are patched in tests).
    """
    plan_hash = hashlib.sha256(ANSWER_PLAN_SYSTEM_PROMPT.encode()).hexdigest()[:8]
    prose_hash = hashlib.sha256(PROSE_GENERATION_SYSTEM_PROMPT.encode()).hexdigest()[:8]
    return f"{plan_hash}/{prose_hash}"


class InterviewGenerationError(Exception):
    """Raised when the model's output couldn't be obtained/parsed after
    all retries (including the in-attempt repair call), at either
    stage. Callers should surface this as a failure to the user — NOT
    synthesize a templated answer, since that would reintroduce a
    deterministic content decision.
    """


# §A — process-lifetime classification metrics. Deliberately a plain
# in-memory counter, not a real metrics backend (none exists in this
# codebase) — good enough to answer "is the fallback rate creeping up"
# from logs/an ad-hoc inspection without adding new infrastructure.
# Resets on process restart, which is an acceptable limitation for a
# first cut; wiring this into a real metrics pipeline is a §R/ops
# concern, not an interview-logic one.
_classification_stats = {"total": 0, "fallback": 0}


def get_classification_metrics() -> dict:
    total = _classification_stats["total"]
    fallback = _classification_stats["fallback"]
    return {
        "total": total,
        "fallback": fallback,
        "fallback_rate": round(fallback / total, 3) if total else 0.0,
    }


async def _call_llm_with_repair(
    *,
    system_prompt: str,
    payload: dict,
    model_cls,
    temperature: float,
    max_tokens: int,
    trace_id: str,
    stage: str,
):
    """One model call, with ONE cheap same-attempt repair fallback if
    the response doesn't parse as JSON or doesn't validate against
    `model_cls`. Far cheaper than a full regeneration, and handles the
    common case (a stray trailing comma, a missing field) without
    spending the outer retry loop's budget on it.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload)},
    ]
    response = await chat_completion(
        model=INTERVIEW_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=INTERVIEW_TIMEOUT_SECONDS,
    )
    content = response.choices[0].message.content

    try:
        return model_cls.model_validate(json.loads(content))
    except Exception as e:
        logger.warning(
            "[trace=%s] stage=%s response failed to parse/validate (%s) — attempting one repair call",
            trace_id, stage, e,
        )
        repair_messages = messages + [
            {"role": "assistant", "content": content},
            {"role": "user", "content": (
                f"That response could not be parsed/validated ({e}). Return ONLY the corrected, "
                "complete, valid JSON object matching the required schema — no prose, no markdown fences."
            )},
        ]
        response = await chat_completion(
            model=INTERVIEW_MODEL,
            messages=repair_messages,
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=max_tokens,
            timeout=INTERVIEW_TIMEOUT_SECONDS,
        )
        repaired_content = response.choices[0].message.content
        return model_cls.model_validate(json.loads(repaired_content))


async def classify_blueprint(question: str, trace_id: str | None = None) -> str:
    trace_id = trace_id or str(uuid4())
    summaries = {key: entry["objective"] for key, entry in BLUEPRINTS.items()}
    _classification_stats["total"] += 1

    try:
        messages = [
            {"role": "system", "content": BLUEPRINT_CLASSIFICATION_PROMPT},
            {"role": "user", "content": json.dumps({"question": question, "blueprints": summaries})},
        ]
        response = await chat_completion(
            model=INTERVIEW_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=MAX_CLASSIFY_TOKENS,
            timeout=CLASSIFY_TIMEOUT_SECONDS,
        )
        content = response.choices[0].message.content
        parsed = BlueprintClassification.model_validate(json.loads(content))

        if parsed.blueprint_key not in BLUEPRINTS:
            logger.warning(
                "[trace=%s] stage=classify classifier returned unknown key '%s', defaulting",
                trace_id, parsed.blueprint_key,
            )
            _classification_stats["fallback"] += 1
            return DEFAULT_BLUEPRINT

        confidence = parsed.confidence if parsed.confidence in _VALID_CLASSIFICATION_CONFIDENCE else "medium"
        competency_tags = sorted({t for t in parsed.competency_tags if t in _VALID_COMPETENCIES})

        logger.info(
            "[trace=%s] stage=classify blueprint=%s confidence=%s competency_tags=%s reason=%r",
            trace_id, parsed.blueprint_key, confidence, competency_tags, parsed.reason,
        )
        return parsed.blueprint_key
    except Exception as e:
        logger.warning(
            "[trace=%s] stage=classify failed, defaulting to %s: %s", trace_id, DEFAULT_BLUEPRINT, e,
        )
        _classification_stats["fallback"] += 1
        metrics = get_classification_metrics()
        if metrics["total"] % 20 == 0:
            # Periodic visibility into drift without logging on every
            # single call — cheap enough to just check the modulus here
            # rather than wiring a scheduled job for a first cut.
            logger.info("[metric=blueprint_classification] %s", metrics)

    return DEFAULT_BLUEPRINT


def _has_any_profile_evidence(context: dict) -> bool:
    profile = context.get("profile", {})
    return bool(
        profile.get("projects") or profile.get("experiences")
        or profile.get("education") or profile.get("github_repos")
    )


def _plan_failed_grounding(ground: GroundingReport) -> bool:
    return bool(ground.unverifiable_claims or ground.possible_fabricated_entities)


def _plan_content_incomplete(plan: AnswerPlan) -> bool:
    if plan.insufficient_context:
        return False
    return not plan.sections or not plan.follow_up_questions or not plan.coaching


def _correction_note(ground: GroundingReport, content_incomplete: bool) -> str:
    parts: list[str] = []
    if _plan_failed_grounding(ground):
        flagged = ground.unverifiable_claims + ground.possible_fabricated_entities
        parts.append(
            "GROUNDING PROBLEM: your previous plan referenced the following item(s), which are NOT "
            "actually present in the candidate's real profile: " + "; ".join(flagged) + ". Do not "
            "repeat any of these items in any form, and do not substitute a different invented item "
            "in their place."
        )
    if content_incomplete:
        parts.append(
            "INCOMPLETE PROBLEM: your previous plan left a required field empty (sections, "
            "follow_up_questions, or coaching) without setting insufficient_context to true. Every "
            "plan for an answerable question must populate all three with real, specific content."
        )
    parts.append("Rewrite the plan from scratch, using only real names/facts genuinely in the profile.")
    return " ".join(parts)


async def generate_answer_plan(
    context: dict, blueprint_key: str, trace_id: str | None = None
) -> tuple[AnswerPlan | None, GroundingReport | None]:
    trace_id = trace_id or str(uuid4())
    base_context = {
        **context,
        "blueprint_library": {blueprint_key: BLUEPRINTS[blueprint_key]},
        "preselected_blueprint": blueprint_key,
    }

    last_plan: AnswerPlan | None = None
    last_ground: GroundingReport | None = None
    correction_note: str | None = None

    for attempt in range(1, MAX_PLAN_ATTEMPTS + 1):
        scoped_context = dict(base_context)
        if correction_note:
            scoped_context["grounding_correction"] = correction_note

        try:
            plan = await _call_llm_with_repair(
                system_prompt=ANSWER_PLAN_SYSTEM_PROMPT,
                payload=scoped_context,
                model_cls=AnswerPlan,
                temperature=0.4,
                max_tokens=MAX_PLAN_TOKENS,
                trace_id=trace_id,
                stage="plan",
            )
        except Exception as e:
            logger.warning(
                "[trace=%s] stage=plan attempt=%d/%d failed (incl. repair): %s",
                trace_id, attempt, MAX_PLAN_ATTEMPTS, e,
            )
            continue

        ground = grounding.validate_plan(plan, context)
        last_plan, last_ground = plan, ground

        grounding_failed = _plan_failed_grounding(ground)
        content_incomplete = _plan_content_incomplete(plan)

        logger.info(
            "[trace=%s] stage=plan attempt=%d/%d blueprint_used=%s grounding_ok=%s content_ok=%s",
            trace_id, attempt, MAX_PLAN_ATTEMPTS, plan.blueprint_used,
            not grounding_failed, not content_incomplete,
        )

        if not grounding_failed and not content_incomplete:
            return plan, ground

        if grounding_failed:
            logger.warning(
                "[trace=%s] stage=plan attempt=%d/%d failed grounding: %s",
                trace_id, attempt, MAX_PLAN_ATTEMPTS,
                ground.unverifiable_claims + ground.possible_fabricated_entities,
            )
        if content_incomplete:
            logger.warning(
                "[trace=%s] stage=plan attempt=%d/%d had incomplete required content",
                trace_id, attempt, MAX_PLAN_ATTEMPTS,
            )
        correction_note = _correction_note(ground, content_incomplete)

    return last_plan, last_ground


async def generate_prose_from_plan(
    context: dict, plan: AnswerPlan, trace_id: str | None = None
) -> ProseOutput:
    trace_id = trace_id or str(uuid4())
    payload = {
        "persona": context.get("persona"),
        "recent_conversation": context.get("recent_conversation", []),
        "correction": context.get("correction"),
        "plan": plan.model_dump(),
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_PROSE_ATTEMPTS + 1):
        try:
            prose = await _call_llm_with_repair(
                system_prompt=PROSE_GENERATION_SYSTEM_PROMPT,
                payload=payload,
                model_cls=ProseOutput,
                temperature=0.5,
                max_tokens=MAX_PROSE_TOKENS,
                trace_id=trace_id,
                stage="prose",
            )
            logger.info(
                "[trace=%s] stage=prose attempt=%d/%d answer_words=%d",
                trace_id, attempt, MAX_PROSE_ATTEMPTS, len((prose.answer or "").split()),
            )
            return prose
        except Exception as e:
            logger.warning(
                "[trace=%s] stage=prose attempt=%d/%d failed (incl. repair): %s",
                trace_id, attempt, MAX_PROSE_ATTEMPTS, e,
            )
            last_error = e

    raise InterviewGenerationError(f"Prose generation failed after {MAX_PROSE_ATTEMPTS} attempts: {last_error}")


def _insufficient_context_output(plan: AnswerPlan | None, reason: str, note: str) -> InterviewLLMOutput:
    return InterviewLLMOutput(
        question_type=(plan.question_type if plan else "") or "insufficient_context",
        blueprint_used=plan.blueprint_used if plan else "",
        insufficient_context=True,
        insufficient_context_reason=reason,
        context_note=note,
    )


async def generate_interview_response(
    context: dict, blueprint_key: str, trace_id: str | None = None
) -> InterviewLLMOutput:
    trace_id = trace_id or str(uuid4())

    if not _has_any_profile_evidence(context):
        logger.warning("[trace=%s] stage=guard candidate profile is completely empty", trace_id)
        return _insufficient_context_output(
            None, "empty_profile",
            "Your profile is empty. Please upload a resume or add experiences/projects to get custom tailored answers.",
        )

    plan, plan_grounding = await generate_answer_plan(context, blueprint_key, trace_id=trace_id)

    if plan is None:
        raise InterviewGenerationError("Answer plan generation failed to produce a parseable plan.")

    if plan.insufficient_context:
        return _insufficient_context_output(
            plan, "model_declined",
            plan.context_note or "Not enough real profile data to answer this question honestly.",
        )

    if plan_grounding is not None and _plan_failed_grounding(plan_grounding):
        logger.warning(
            "[trace=%s] stage=plan answer plan still failed grounding after all retries — "
            "returning insufficient_context instead of building prose from an ungrounded plan. Flagged: %s",
            trace_id, plan_grounding.unverifiable_claims + plan_grounding.possible_fabricated_entities,
        )
        return _insufficient_context_output(
            plan, "grounding_rejected",
            "Couldn't build a fully grounded answer from your real profile data for this question — "
            "the draft kept referencing details that aren't actually in your profile.",
        )

    if _plan_content_incomplete(plan):
        logger.warning(
            "[trace=%s] stage=plan proceeding with incomplete required content after all retries "
            "(question_type=%s, blueprint_used=%s)",
            trace_id, plan.question_type, plan.blueprint_used,
        )

    prose = await generate_prose_from_plan(context, plan, trace_id=trace_id)

    output = InterviewLLMOutput(
        question_type=plan.question_type,
        blueprint_used=plan.blueprint_used,
        competencies=plan.competencies,
        stories_used=plan.stories_used,
        answer=prose.answer,
        answer_short=prose.answer_short,
        follow_up_questions=plan.follow_up_questions,
        coaching=plan.coaching,
        insufficient_context=False,
        insufficient_context_reason="",
        context_note="",
        claims_needing_verification=plan.claims_needing_verification,
        prompt_version=_compute_prompt_version(),
    )

    output.grounding = grounding.validate_answer(output, context)
    if output.grounding.unverifiable_claims or output.grounding.possible_fabricated_entities:
        logger.warning(
            "[trace=%s] stage=post_prose_scan flagged %d unverifiable claim(s), %d possible fabricated "
            "entit(y/ies) despite an already-grounded plan: %s / %s",
            trace_id,
            len(output.grounding.unverifiable_claims),
            len(output.grounding.possible_fabricated_entities),
            output.grounding.unverifiable_claims,
            output.grounding.possible_fabricated_entities,
        )

    logger.info(
        "[trace=%s] stage=complete question_type=%s blueprint_used=%s insufficient_context=%s",
        trace_id, output.question_type, output.blueprint_used, output.insufficient_context,
    )
    return output