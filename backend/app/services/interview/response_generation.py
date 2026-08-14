# backend/app/services/interview/response_generation.py
"""Two-stage generation for the Interview Response Agent:

1. classify_blueprint() — a cheap, small-payload call that picks ONE
   blueprint key from the blueprint library based on just the question
   and each blueprint's one-line objective. Called by the API layer
   BEFORE context_builder.build_interview_context(), since Phase 0's
   retrieval layer needs the blueprint's competency hints to rank
   evidence (see context_builder.py) — this is the one call-order
   change from the original two-stage design.
2. generate_interview_response() — the full reasoning call, given only
   the ONE selected blueprint instead of the entire library, PLUS the
   Engineering Identity framing layer, recent conversation turns, and
   an optional correction to honor as a hard constraint.

This module does not decide interview CONTENT itself — it only (a)
calls the model, (b) retries on genuinely unparseable output, (c) runs
the deterministic, non-LLM grounding pass afterward
(services/interview/grounding.py). None of that is a content decision.
If generation genuinely fails, we surface that failure rather than
writing a fallback answer ourselves.
"""
import json
import logging

from app.core.llm import chat_completion, MODEL

logger = logging.getLogger(__name__)

from app.prompts.interview.interview_response import (
    BLUEPRINT_CLASSIFICATION_PROMPT,
    INTERVIEW_RESPONSE_SYSTEM_PROMPT,
)
from app.schemas.interview.interview_response import BlueprintClassification, InterviewLLMOutput
from app.services.interview import grounding
from app.services.interview.blueprints import BLUEPRINTS

MAX_ATTEMPTS = 3
DEFAULT_BLUEPRINT = "behavioral_default"

MAX_CLASSIFY_TOKENS = 200
MAX_GENERATE_TOKENS = 1200
INTERVIEW_MODEL = "llama-3.3-70b-versatile"


class InterviewGenerationError(Exception):
    """Raised when the model's output couldn't be obtained/parsed after
    all retries. Callers should surface this as a failure to the user —
    NOT synthesize a templated answer, since that would reintroduce a
    deterministic content decision.
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


async def generate_interview_response(context: dict, blueprint_key: str) -> InterviewLLMOutput:
    """`blueprint_key` is now REQUIRED — always the output of a prior
    classify_blueprint(question) call made by the API layer before
    context_builder.build_interview_context(), so retrieval and
    generation agree on which blueprint this question is being answered
    under (previously this function classified independently, AFTER
    context had already been built with no knowledge of the blueprint).
    """
    profile = context.get("profile", {})
    has_projects = bool(profile.get("projects"))
    has_experiences = bool(profile.get("experiences"))
    has_education = bool(profile.get("education"))
    has_github_repos = bool(profile.get("github_repos"))

    if not (has_projects or has_experiences or has_education or has_github_repos):
        logger.warning("Candidate profile is completely empty. Returning insufficient context.")
        return InterviewLLMOutput(
            question_type="insufficient_context",
            blueprint_used="",
            competencies=[],
            stories_used=[],
            answer="",
            answer_short="",
            follow_up_questions=[],
            coaching=[],
            insufficient_context=True,
            context_note="Your profile is empty. Please upload a resume or add experiences/projects to get custom tailored answers."
        )

    scoped_context = {
        **context,
        "blueprint_library": {blueprint_key: BLUEPRINTS[blueprint_key]},
        "preselected_blueprint": blueprint_key,
    }

    prompt_size_chars = len(INTERVIEW_RESPONSE_SYSTEM_PROMPT) + len(json.dumps(scoped_context))
    logger.info(
        "Interview generation prompt size: ~%d chars (~%d tokens, ~%d tokens reserved for completion)",
        prompt_size_chars,
        prompt_size_chars // 4,
        MAX_GENERATE_TOKENS,
    )

    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        logger.info(
            "Requesting interview response (attempt %d/%d) for question=%r using blueprint=%r...",
            attempt,
            MAX_ATTEMPTS,
            context['question'],
            blueprint_key,
        )
        try:
            messages = [
                {"role": "system", "content": INTERVIEW_RESPONSE_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(scoped_context)},
            ]
            response = await chat_completion(
                model=INTERVIEW_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=MAX_GENERATE_TOKENS,
            )
            content = response.choices[0].message.content
            logger.debug("Raw interview response JSON: %s", content)
            parsed = InterviewLLMOutput.model_validate(json.loads(content))
            logger.info("Blueprint used: %s", parsed.blueprint_used)

            parsed.grounding = grounding.validate_answer(parsed, context)
            if parsed.grounding.unverifiable_claims or parsed.grounding.possible_fabricated_entities:
                logger.warning(
                    "Grounding flagged %d unverifiable claim(s), %d possible fabricated entit(y/ies): %s / %s",
                    len(parsed.grounding.unverifiable_claims),
                    len(parsed.grounding.possible_fabricated_entities),
                    parsed.grounding.unverifiable_claims,
                    parsed.grounding.possible_fabricated_entities,
                )

            return parsed
        except Exception as e:
            logger.warning("Attempt %d/%d failed to parse: %s", attempt, MAX_ATTEMPTS, e)
            last_error = e

    raise InterviewGenerationError(
        f"Interview response generation failed after {MAX_ATTEMPTS} attempts: {last_error}"
    )