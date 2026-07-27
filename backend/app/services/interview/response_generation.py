"""Two-stage generation for the Interview Response Agent:

1. classify_blueprint() — a cheap, small-payload call that picks ONE
   blueprint key from the ~24-entry library based on just the question
   and each blueprint's one-line objective.
2. generate_interview_response() — the full reasoning call (question
   classification, competency judgment, story selection, sufficiency
   judgment, answer generation), but now given only the ONE selected
   blueprint instead of the entire library. This is the main fix for
   the context-window overflow that was causing Ollama to silently
   truncate the prompt and return "{}" — the full blueprint library was
   by far the largest fixed cost in every call.

This module does not decide interview CONTENT itself — it only (a)
calls the model, (b) retries on genuinely unparseable output, and (c)
picks which blueprint to hand to step 2, which is a routing decision,
not a content decision. If generation genuinely fails, we surface that
failure rather than writing a fallback answer ourselves.
"""
import json

from app.core.llm import chat_completion, MODEL
from app.prompts.interview_response import (
    BLUEPRINT_CLASSIFICATION_PROMPT,
    INTERVIEW_RESPONSE_SYSTEM_PROMPT,
)
from app.schemas.interview_response import BlueprintClassification, InterviewLLMOutput
from app.services.interview.blueprints import BLUEPRINTS

MAX_ATTEMPTS = 3
DEFAULT_BLUEPRINT = "behavioral_default"


class InterviewGenerationError(Exception):
    """Raised when the model's output couldn't be obtained/parsed after
    all retries. Callers should surface this as a failure to the user —
    NOT synthesize a templated answer, since that would reintroduce a
    deterministic content decision.
    """


async def classify_blueprint(question: str) -> str:
    """Cheap pass: sends only the question + {key: objective} for every
    blueprint (not the full sections/notes), and returns a single key.
    Falls back to a generic default on any failure rather than raising —
    this step is a routing optimization, not something worth failing the
    whole request over.
    """
    summaries = {key: entry["objective"] for key, entry in BLUEPRINTS.items()}
    try:
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": BLUEPRINT_CLASSIFICATION_PROMPT},
                {"role": "user", "content": json.dumps({"question": question, "blueprints": summaries})},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=2000,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw blueprint classification JSON:\n{content}", flush=True)
        parsed = BlueprintClassification.model_validate(json.loads(content))
        if parsed.blueprint_key in BLUEPRINTS:
            print(f"[TRACING] Classified blueprint: {parsed.blueprint_key} ({parsed.reason})", flush=True)
            return parsed.blueprint_key
        print(f"[TRACING] Classifier returned unknown key '{parsed.blueprint_key}', defaulting", flush=True)
    except Exception as e:
        print(f"[TRACING] Blueprint classification failed, defaulting to {DEFAULT_BLUEPRINT}: {e}", flush=True)

    return DEFAULT_BLUEPRINT


async def generate_interview_response(context: dict) -> InterviewLLMOutput:
    profile = context.get("profile", {})
    has_projects = bool(profile.get("projects"))
    has_experiences = bool(profile.get("experiences"))
    has_education = bool(profile.get("education"))

    if not (has_projects or has_experiences or has_education):
        print("[TRACING] Candidate profile is completely empty. Returning insufficient context.", flush=True)
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

    blueprint_key = await classify_blueprint(context["question"])

    # Only the ONE selected blueprint goes to the generation call — this
    # is the main payload reduction versus sending all ~24 entries.
    scoped_context = {
        **context,
        "blueprint_library": {blueprint_key: BLUEPRINTS[blueprint_key]},
        "preselected_blueprint": blueprint_key,
    }

    prompt_size_chars = len(INTERVIEW_RESPONSE_SYSTEM_PROMPT) + len(json.dumps(scoped_context))
    print(
        f"[TRACING] Interview generation prompt size: ~{prompt_size_chars} chars "
        f"(~{prompt_size_chars // 4} tokens)",
        flush=True,
    )

    last_error: Exception | None = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(
            f"[TRACING] Requesting interview response (attempt {attempt}/{MAX_ATTEMPTS}) "
            f"for question={context['question']!r} using blueprint={blueprint_key!r}...",
            flush=True,
        )
        try:
            response = await chat_completion(
                model=MODEL,
                messages=[
                    {"role": "system", "content": INTERVIEW_RESPONSE_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(scoped_context)},
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=3000,
            )
            content = response.choices[0].message.content
            print(f"[TRACING] Raw interview response JSON:\n{content}", flush=True)
            parsed = InterviewLLMOutput.model_validate(json.loads(content))
            print(f"[TRACING] Blueprint used: {parsed.blueprint_used}", flush=True)
            return parsed
        except Exception as e:
            print(f"[TRACING] Attempt {attempt}/{MAX_ATTEMPTS} failed to parse: {e}", flush=True)
            last_error = e

    raise InterviewGenerationError(
        f"Interview response generation failed after {MAX_ATTEMPTS} attempts: {last_error}"
    )