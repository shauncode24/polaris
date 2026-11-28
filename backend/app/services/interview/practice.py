"""Practice mode: reviews the user's answer to a kit question, saves it, and
reports how much of the kit has been covered.

A model says which headings of the question's answer outline the answer covers,
and what to improve. It isn't taken at its word:

  * a heading counts as covered only with a quote that is really in the answer
  * the score is worked out here: the share of headings so covered
  * a remark that brings in a figure or technology found nowhere in the record,
    the question or the answer is dropped

Separately, and without a model, the answer is checked for figures and
technologies the user's record doesn't show (record_check.py). When the model
can't be used the answer is still saved with that check, unscored.
"""
import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLMError, Prompt, llm_json
from app.models.interview_kit import InterviewKit, InterviewQuestion, PracticeAttempt
from app.prompts.interview.practice_review import PRACTICE_REVIEW_SYSTEM_PROMPT
from app.schemas.interview.kit import CATEGORIES, AnswerOutline
from app.schemas.interview.practice import (
    AttemptFeedback,
    CategoryProgress,
    HeadingFeedback,
    KitProgress,
    PracticeAttemptView,
    PracticeReviewReply,
    QuestionProgress,
)
from app.services.interview.kit_answers import answer_outlines
from app.services.interview.kit_evidence import skill_names
from app.services.interview.kit_store import get_kit
from app.services.interview.record_check import Record, load_record, unrecorded
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.job_intelligence.cleanup import plain_text

_MIN_QUOTED_WORDS = 2
_MAX_RECORD_LINES = 12
_ANSWER_TOKENS = 1200

_UNSCORED = "Your answer is saved but wasn't reviewed, so it has no score."


async def find_question(db: AsyncSession, user_id, question_id) -> tuple[InterviewQuestion, InterviewKit] | None:
    """The user's question and its kit, or None."""
    found = (await db.execute(
        select(InterviewQuestion, InterviewKit)
        .join(InterviewKit, InterviewKit.id == InterviewQuestion.kit_id)
        .where(InterviewQuestion.id == question_id, InterviewKit.user_id == user_id)
    )).first()
    return None if found is None else (found[0], found[1])


def _words(text: str) -> str:
    """The text's words alone, for finding a quote however it is punctuated."""
    kept = "".join(c if c.isalnum() or c in "%$+#" else " " for c in plain_text(text).casefold())
    return f" {' '.join(kept.split())} "


def _quoted(quote: str, answer: str) -> bool:
    words = _words(quote)
    return len(words.split()) >= _MIN_QUOTED_WORDS and words in _words(answer)


def _record_lines(outline: AnswerOutline) -> list[str]:
    facts = [fact.text for section in outline.sections for fact in section.facts]
    facts += [fact.text for fact in outline.other_facts]
    return list(dict.fromkeys(facts))[:_MAX_RECORD_LINES]


async def _model_review(question: InterviewQuestion, outline: AnswerOutline, answer: str) -> PracticeReviewReply:
    """Raises an `LLMError`."""
    headings = [section.heading for section in outline.sections]

    def one_per_heading(payload: dict) -> dict:
        entries = payload.get("headings")
        if not isinstance(entries, list):
            raise ValueError("'headings' must be a list")
        by_name: dict[str, dict] = {}
        for entry in entries:
            if isinstance(entry, dict) and isinstance(entry.get("heading"), str):
                by_name.setdefault(entry["heading"].strip().casefold(), entry)
        missing = [h for h in headings if h.casefold() not in by_name]
        if missing:
            raise ValueError(f"no verdict for: {', '.join(missing)}")
        return {**payload, "headings": [{**by_name[h.casefold()], "heading": h} for h in headings]}

    asked = {
        "category": question.category,
        "question": question.text,
        "headings": [{"heading": s.heading, "covers": s.prompt} for s in outline.sections],
        "record": _record_lines(outline),
        "answer": answer,
    }
    reply = await llm_json(
        Prompt(PRACTICE_REVIEW_SYSTEM_PROMPT, asked), PracticeReviewReply,
        label="interview_practice_review", expect=("headings",), prepare=one_per_heading,
        max_tokens=_ANSWER_TOKENS, repair=True,
    )
    return reply.value


def _warnings(figures: list[str], technologies: list[str]) -> list[str]:
    warnings = []
    if figures:
        warnings.append(
            f"Your record doesn't show these figures: {', '.join(figures)}. That is fine in a design or a "
            "\"how would you\" answer; if you say it happened, be sure it did."
        )
    if technologies:
        warnings.append(
            f"Your record doesn't show these technologies: {', '.join(technologies)}. Say you've used them only "
            "if you have, and if so add them to your profile."
        )
    return warnings


async def _feedback(
    question: InterviewQuestion, outline: AnswerOutline, record: Record, names: dict, answer: str,
) -> tuple[AttemptFeedback, float | None]:
    outside = unrecorded(record, answer, given_figures=question.text, names=names)
    feedback = AttemptFeedback(
        headings=[HeadingFeedback(heading=s.heading, prompt=s.prompt) for s in outline.sections],
        unrecorded_figures=outside.figures, unrecorded_technologies=outside.technologies,
        warnings=_warnings(outside.figures, outside.technologies),
    )
    try:
        review = await _model_review(question, outline, answer)
    except LLMError as e:
        feedback.notice = f"{_UNSCORED} {e}"
        return feedback, None

    said = "\n".join([question.text, answer])

    def grounded(remark: str) -> str | None:
        remark = " ".join(remark.split())
        return remark if remark and not unrecorded(record, remark, also_said=said, names=names) else None

    for heading, verdict in zip(feedback.headings, review.headings):
        heading.covered = verdict.covered and _quoted(verdict.quote, answer)
        heading.quote = verdict.quote.strip() if heading.covered else None
        # A remark on a part the model wrongly counted would read as if it were there.
        heading.note = grounded(verdict.note) if heading.covered == verdict.covered else None
    feedback.overall = grounded(review.overall)
    covered = sum(bool(h.covered) for h in feedback.headings)
    return feedback, round(covered / len(feedback.headings), 2)


def _view(row: PracticeAttempt) -> PracticeAttemptView:
    return PracticeAttemptView(
        id=row.id, question_id=row.question_id, answer=row.answer, created_at=row.created_at, score=row.score,
        feedback=AttemptFeedback.model_validate(row.feedback_json),
    )


async def review_answer(db: AsyncSession, user_id, question_id, answer: str) -> PracticeAttemptView | None:
    """Reviews the answer and saves it as a new attempt. None when the user has
    no such question. A model failure, including a used-up daily limit, is never
    raised: the feedback's `notice` says what it cost.
    """
    found = await find_question(db, user_id, question_id)
    if found is None:
        return None
    question, kit = found
    outlines = await answer_outlines(db, user_id, kit.job_intelligence_id, kit.version)
    job = await get_job_intelligence(db, user_id, kit.job_intelligence_id)
    if outlines is None or job is None:  # the job was deleted meanwhile
        return None
    outline = next(o for o in outlines.outlines if o.question_id == question.id)
    names = await skill_names(db, job, set(question.skills))
    record = await load_record(db, user_id)

    feedback, score = await _feedback(question, outline, record, names, answer)

    if await find_question(db, user_id, question_id) is None:  # deleted while it was being reviewed
        return None
    row = PracticeAttempt(
        id=uuid.uuid4(), user_id=user_id, question_id=question_id, answer=answer,
        feedback_json=feedback.model_dump(mode="json"), score=score,
    )
    db.add(row)
    await db.commit()
    return _view(row)


async def list_attempts(db: AsyncSession, user_id, question_id) -> list[PracticeAttemptView] | None:
    """The user's attempts at a question, newest first. None when it isn't theirs."""
    if await find_question(db, user_id, question_id) is None:
        return None
    rows = await db.scalars(
        select(PracticeAttempt)
        .where(PracticeAttempt.user_id == user_id, PracticeAttempt.question_id == question_id)
        .order_by(PracticeAttempt.created_at.desc())
    )
    return [_view(row) for row in rows]


def _weakest(categories: list[CategoryProgress], scored: dict[str, float]) -> str | None:
    """The category answered least well: its scores over all its questions, an
    unanswered or unscored one counting nothing, then the share practised. None
    while they all stand alike, as before any practice.
    """
    standing = {
        c.category: (scored.get(c.category, 0.0) / c.total, c.practised / c.total) for c in categories
    }
    if len(set(standing.values())) < 2:
        return None
    return min(standing, key=standing.get)


async def kit_progress(
    db: AsyncSession, user_id, job_intelligence_id, version: int | None = None,
) -> KitProgress | None:
    """How much of a saved kit has been practised, the newest unless a version
    is named. None when the user has no such kit.
    """
    saved = await get_kit(db, user_id, job_intelligence_id, version)
    if saved is None:
        return None
    attempts: dict = defaultdict(list)  # question id -> scores, newest first
    rows = await db.execute(
        select(PracticeAttempt.question_id, PracticeAttempt.score)
        .where(PracticeAttempt.user_id == user_id,
               PracticeAttempt.question_id.in_([q.id for q in saved.questions]))
        .order_by(PracticeAttempt.created_at.desc())
    )
    for question_id, score in rows:
        attempts[question_id].append(score)

    questions = [
        QuestionProgress(
            question_id=q.id, category=q.category, topic=q.topic, text=q.text, attempts=len(attempts[q.id]),
            latest_score=next((s for s in attempts[q.id] if s is not None), None),
        )
        for q in saved.questions
    ]
    categories, totals = [], {}
    for category in CATEGORIES:
        mine = [q for q in questions if q.category == category]
        if not mine:
            continue
        scores = [q.latest_score for q in mine if q.latest_score is not None]
        totals[category] = sum(scores)
        categories.append(CategoryProgress(
            category=category, total=len(mine), practised=sum(q.attempts > 0 for q in mine),
            average_score=round(sum(scores) / len(scores), 2) if scores else None,
        ))
    return KitProgress(
        version=saved.kit.version, total=len(questions), practised=sum(c.practised for c in categories),
        weakest=_weakest(categories, totals), categories=categories, questions=questions,
    )
