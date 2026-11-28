"""Builds the interview kit for one job: outlines its questions, asks the model
to word them for that job, and matches each to the user's evidence.

The call that words the questions is sent the job only, never anything about the
candidate. It can't add, drop or retag a question: each reply is matched to an
outline slot, and a slot with no usable wording keeps the standard one. So a kit
always comes out, with a notice when the model's wording is missing from some or
all of it. The evidence is matched separately (kit_evidence.py).
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLMError, Prompt, llm_json
from app.prompts.interview.kit_questions import KIT_QUESTIONS_SYSTEM_PROMPT
from app.schemas.interview.kit import (
    MAX_QUESTION_LENGTH,
    InterviewKitDraft,
    KitQuestion,
    QuestionWordingReply,
)
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.services.evidence.matching import skill_aliases
from app.services.interview.kit_evidence import map_evidence
from app.services.interview.kit_outline import build_outline, names_topic, spellings
from app.services.job_intelligence.builder import get_job_intelligence

_MIN_QUESTION_LENGTH = 15
_MAX_RESPONSIBILITIES = 10
_ANSWER_TOKENS = 2500

_NONE_WORDED = "The questions use standard wording built from the job's requirements."


def _skill_names(job: JobIntelligenceProfile, aliases: dict[str, set[str]]) -> dict[str, set[str]]:
    skills = [*job.enriched_required_skills, *job.enriched_implicit_skills, *job.enriched_nice_to_have]
    return {s.canonical: spellings(s, aliases) for s in skills}


def _usable(text: str, question: KitQuestion, names: dict[str, set[str]]) -> bool:
    if not _MIN_QUESTION_LENGTH <= len(text) <= MAX_QUESTION_LENGTH:
        return False
    # A technical question that doesn't name its skill may be about something
    # else, and would then be matched to the wrong evidence.
    if question.category == "technical_depth" and question.skills:
        return any(names_topic(text, names[skill]) for skill in question.skills)
    return True


async def _word_questions(
    job: JobIntelligenceProfile, seniority: str, outline: dict[str, KitQuestion], names: dict[str, set[str]],
) -> dict[str, str]:
    """slot id -> the model's wording, for the slots where it can be used.
    Raises an `LLMError`.
    """
    def keep_usable(payload: dict) -> dict:
        entries = payload.get("questions")
        if not isinstance(entries, list):
            raise ValueError("'questions' must be a list")
        kept: dict[str, str] = {}
        used: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            slot, text = entry.get("id"), entry.get("question")
            if not isinstance(slot, str) or not isinstance(text, str) or slot not in outline or slot in kept:
                continue
            text = " ".join(text.split())
            if text.casefold() not in used and _usable(text, outline[slot], names):
                kept[slot] = text
                used.add(text.casefold())
        if not kept:
            raise ValueError("none of the questions can be used")
        return {"questions": [{"id": slot, "question": text} for slot, text in kept.items()]}

    asked = {
        "role": job.role,
        "seniority": seniority,
        "responsibilities": job.responsibilities[:_MAX_RESPONSIBILITIES],
        "questions": [
            {"id": slot, "category": q.category, "topic": q.topic, "outline": q.text}
            for slot, q in outline.items()
        ],
    }
    reply = await llm_json(
        Prompt(KIT_QUESTIONS_SYSTEM_PROMPT, asked), QuestionWordingReply,
        label="interview_kit_questions", expect=("questions",), prepare=keep_usable,
        temperature=0.4, max_tokens=_ANSWER_TOKENS, repair=True,
    )
    return {entry.id: entry.question for entry in reply.value.questions}


async def generate_interview_kit(db: AsyncSession, user_id, job_intelligence_id) -> InterviewKitDraft | None:
    """The kit for this job; not saved. None when the user has no such job. A
    model failure, including a used-up daily limit, is never raised: the kit's
    `notice` says what it cost.
    """
    job = await get_job_intelligence(db, user_id, job_intelligence_id)
    if job is None:
        return None
    canonicals = {s.canonical for s in
                  [*job.enriched_required_skills, *job.enriched_implicit_skills, *job.enriched_nice_to_have]}
    aliases = await skill_aliases(db, canonicals)
    questions = build_outline(job, aliases)
    outline = {f"q{number}": question for number, question in enumerate(questions, start=1)}
    seniority = job.seniority_signal.level

    notice = None
    try:
        worded = await _word_questions(job, seniority, outline, _skill_names(job, aliases))
    except LLMError as e:
        worded, notice = {}, f"{_NONE_WORDED} {e}"
    else:
        missing = len(outline) - len(worded)
        if missing:
            notice = (
                f"{missing} of {len(outline)} questions use standard wording, because the AI's version "
                "of them couldn't be used."
            )

    questions = [
        question.model_copy(update={"text": worded[slot], "origin": "model"}) if slot in worded else question
        for slot, question in outline.items()
    ]
    mapping = await map_evidence(db, user_id, job, questions)
    return InterviewKitDraft(
        seniority=seniority,
        notice=notice,
        evidence_mapped_at=mapping.mapped_at,
        evidence_notice=mapping.notice,
        questions=[
            question.model_copy(update={"evidence_refs": refs, "thin_evidence": not refs})
            for question, refs in zip(questions, mapping.refs)
        ],
    )
