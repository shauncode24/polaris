# backend/app/services/interview/response_generation.py
"""Phase 1 pipeline (implementation plan §F/§G/§H/§I, target
architecture diagram): classification -> plan -> pre-prose validation
(reject/re-plan once) -> prose -> post-prose grounding scan.

classify_blueprint() is unchanged from Phase 0 — cheap, temp-0, called
by the API layer BEFORE context_builder.build_interview_context() so
retrieval can use the blueprint's competency hints.

generate_interview_response() is an orchestrator over two narrower
calls instead of one overloaded one:
  1. generate_answer_plan() — the ONLY stage that sees the raw profile.
     Produces a structured AnswerPlan with explicit fact citations.
     Each attempt is checked against TWO independent conditions before
     being accepted:
       - grounding.validate_plan() — did it cite anything not actually
         in the real profile? (implementation plan §H)
       - _plan_content_incomplete() — did it leave a required field
         (sections/follow_up_questions/coaching) empty without
         legitimately setting insufficient_context? (implementation
         plan §I, applied here rather than post-hoc, since content
         completeness is a planning decision, not a prose one)
     Either failure produces a specific, targeted correction message
     fed back into the next attempt, within the same shared attempt
     budget — this is deliberately not two separate unlimited retry
     loops, since an attempt can (and often will) fail both checks at
     once and should only cost one retry either way.
  2. generate_prose_from_plan() — never sees the raw profile, only the
     already-validated plan. Restyles it into spoken prose.

The "no fabricated fallback answer on total LLM failure" philosophy is
unchanged: genuine failures raise InterviewGenerationError and are
surfaced as a 502, never silently replaced with a templated answer.
"""
import json
import logging

from app.core.llm import chat_completion, MODEL

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

MAX_CLASSIFY_TOKENS = 200
MAX_PLAN_TOKENS = 1400
MAX_PROSE_TOKENS = 700
INTERVIEW_MODEL = "llama-3.3-70b-versatile"

# Plan generation gets up to this many total attempts. This single
# budget covers genuine parse/call failures AND both the grounding
# retry and the content-completeness retry — a failure on any one of
# those axes consumes one attempt, same as a malformed-JSON failure
# would, rather than each axis getting its own separate budget.
MAX_PLAN_ATTEMPTS = 3
MAX_PROSE_ATTEMPTS = 2


class InterviewGenerationError(Exception):
    """Raised when the model's output couldn't be obtained/parsed after
    all retries, at either stage. Callers should surface this as a
    failure to the user — NOT synthesize a templated answer, since that
    would reintroduce a deterministic content decision.
    """


async def classify_blueprint(question: str) -> str:
    summaries = {key: entry["objective"] for key, entry in BLUEPRINTS.items()}
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
        )
        content = response.choices[0].message.content
        logger.debug("Raw blueprint classification JSON: %s", content)
        parsed = BlueprintClassification.model_validate(json.loads(content))
        if parsed.blueprint_key in BLUEPRINTS:
            logger.info("Classified blueprint: %s (%s)", parsed.blueprint_key, parsed.reason)
            return parsed.blueprint_key
        logger.warning("Classifier returned unknown key '%s', defaulting", parsed.blueprint_key)
    except Exception as e:
        logger.warning("Blueprint classification failed, defaulting to %s: %s", DEFAULT_BLUEPRINT, e)

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
    """Implementation plan §I — a plan that isn't legitimately claiming
    insufficient_context must still populate its required fields. An
    empty "sections" list, or empty "follow_up_questions"/"coaching",
    reads as the model quietly truncating rather than doing the work —
    the same failure mode the audit flagged for the old single-call
    pipeline, just checked one stage earlier now that there's a
    structured plan to check it against.
    """
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


async def _call_plan_llm(scoped_context: dict) -> AnswerPlan:
    response = await chat_completion(
        model=INTERVIEW_MODEL,
        messages=[
            {"role": "system", "content": ANSWER_PLAN_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(scoped_context)},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
        max_tokens=MAX_PLAN_TOKENS,
    )
    content = response.choices[0].message.content
    logger.debug("Raw answer plan JSON: %s", content)
    return AnswerPlan.model_validate(json.loads(content))


async def generate_answer_plan(
    context: dict, blueprint_key: str
) -> tuple[AnswerPlan | None, GroundingReport | None]:
    """Returns (plan, grounding_report). `plan` is None only if every
    attempt failed outright (malformed JSON / call error) with no
    parseable plan to even report on. If a plan WAS produced but its
    final attempt still fails grounding and/or content-completeness, it
    is still returned alongside its (failing) GroundingReport — the
    caller decides the user-facing outcome; this function's job is only
    to try, validate on both axes, and retry-with-feedback.
    """
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
            plan = await _call_plan_llm(scoped_context)
        except Exception as e:
            logger.warning("Answer plan attempt %d/%d failed to parse: %s", attempt, MAX_PLAN_ATTEMPTS, e)
            continue

        ground = grounding.validate_plan(plan, context)
        last_plan, last_ground = plan, ground

        grounding_failed = _plan_failed_grounding(ground)
        content_incomplete = _plan_content_incomplete(plan)

        if not grounding_failed and not content_incomplete:
            return plan, ground

        if grounding_failed:
            logger.warning(
                "Answer plan attempt %d/%d failed grounding: %s",
                attempt, MAX_PLAN_ATTEMPTS,
                ground.unverifiable_claims + ground.possible_fabricated_entities,
            )
        if content_incomplete:
            logger.warning(
                "Answer plan attempt %d/%d had incomplete required content "
                "(empty sections/follow_up_questions/coaching without insufficient_context)",
                attempt, MAX_PLAN_ATTEMPTS,
            )
        correction_note = _correction_note(ground, content_incomplete)

    return last_plan, last_ground


async def generate_prose_from_plan(context: dict, plan: AnswerPlan) -> ProseOutput:
    """Never receives the raw profile — only the plan, persona, recent
    conversation, and any correction. Cannot introduce a new fact
    because it has nothing to invent one from.
    """
    payload = {
        "persona": context.get("persona"),
        "recent_conversation": context.get("recent_conversation", []),
        "correction": context.get("correction"),
        "plan": plan.model_dump(),
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_PROSE_ATTEMPTS + 1):
        try:
            response = await chat_completion(
                model=INTERVIEW_MODEL,
                messages=[
                    {"role": "system", "content": PROSE_GENERATION_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload)},
                ],
                response_format={"type": "json_object"},
                temperature=0.5,
                max_tokens=MAX_PROSE_TOKENS,
            )
            content = response.choices[0].message.content
            logger.debug("Raw prose JSON: %s", content)
            return ProseOutput.model_validate(json.loads(content))
        except Exception as e:
            logger.warning("Prose generation attempt %d/%d failed: %s", attempt, MAX_PROSE_ATTEMPTS, e)
            last_error = e

    raise InterviewGenerationError(f"Prose generation failed after {MAX_PROSE_ATTEMPTS} attempts: {last_error}")


def _insufficient_context_output(plan: AnswerPlan | None, note: str) -> InterviewLLMOutput:
    return InterviewLLMOutput(
        question_type=(plan.question_type if plan else "") or "insufficient_context",
        blueprint_used=plan.blueprint_used if plan else "",
        insufficient_context=True,
        context_note=note,
    )


async def generate_interview_response(context: dict, blueprint_key: str) -> InterviewLLMOutput:
    """`blueprint_key` is REQUIRED — always the output of a prior
    classify_blueprint(question) call made by the API layer before
    context_builder.build_interview_context().
    """
    if not _has_any_profile_evidence(context):
        logger.warning("Candidate profile is completely empty. Returning insufficient context.")
        return InterviewLLMOutput(
            question_type="insufficient_context",
            insufficient_context=True,
            context_note="Your profile is empty. Please upload a resume or add experiences/projects to get custom tailored answers.",
        )

    plan, plan_grounding = await generate_answer_plan(context, blueprint_key)

    if plan is None:
        raise InterviewGenerationError("Answer plan generation failed to produce a parseable plan.")

    if plan.insufficient_context:
        return _insufficient_context_output(
            plan, plan.context_note or "Not enough real profile data to answer this question honestly."
        )

    if plan_grounding is not None and _plan_failed_grounding(plan_grounding):
        logger.warning(
            "Answer plan still failed grounding after retries — returning insufficient_context "
            "instead of building prose from an ungrounded plan. Flagged: %s",
            plan_grounding.unverifiable_claims + plan_grounding.possible_fabricated_entities,
        )
        return _insufficient_context_output(
            plan,
            "Couldn't build a fully grounded answer from your real profile data for this question — "
            "the draft kept referencing details that aren't actually in your profile.",
        )

    if _plan_content_incomplete(plan):
        # Content-completeness is a soft signal, not a hard gate (unlike
        # grounding above): a plan missing e.g. one follow-up question is
        # still safe to serve — it's just weaker than it should be. Log
        # for visibility and proceed with what the retries produced,
        # same graceful-degradation posture used throughout this codebase.
        logger.warning(
            "Proceeding with an answer plan that still has incomplete required content after all "
            "retries (question_type=%s, blueprint_used=%s)",
            plan.question_type, plan.blueprint_used,
        )

    prose = await generate_prose_from_plan(context, plan)

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
        context_note="",
        claims_needing_verification=plan.claims_needing_verification,
    )

    output.grounding = grounding.validate_answer(output, context)
    if output.grounding.unverifiable_claims or output.grounding.possible_fabricated_entities:
        # Post-prose scan is advisory only (see grounding.py docstring) —
        # the plan already passed validate_plan(), so this is logged for
        # visibility, not acted on.
        logger.warning(
            "Post-prose scan flagged %d unverifiable claim(s), %d possible fabricated entit(y/ies) "
            "despite an already-grounded plan: %s / %s",
            len(output.grounding.unverifiable_claims),
            len(output.grounding.possible_fabricated_entities),
            output.grounding.unverifiable_claims,
            output.grounding.possible_fabricated_entities,
        )

    return output