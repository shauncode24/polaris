"""The answer outline for each question of a saved interview kit: the headings of
a good answer, with the user's own words placed under the ones they speak to.

No model writes any of it, so it can't say anything the record doesn't. A fact
is a line of the matched project or role, unchanged, or its title and dates, or
a count of solved LeetCode problems. Everything else is a fixed prompt about what
to cover. (The interview grounding gate checks only figures and a few invented
names in model-written text, too little to rely on for wording of its own.)

Where a line goes:

  the lines showing what the question asks  "What you did" (or its equivalent)
  of those, ones stating a measured change  "Result", if others remain above
  the rest of the project or role           listed apart, under no heading, so a
                                            figure from other work is never
                                            offered as this answer's result

Outlines are built when asked for, from the record as it is then: a hidden or
removed item or skill is gone from them at once. Nothing is stored.
"""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Experience, Project
from app.models.inference import ProjectClaimAuditReview
from app.models.interview_kit import InterviewQuestion
from app.schemas.interview.kit import (
    AnswerOutline,
    KitOutlines,
    OutlineFact,
    OutlineSection,
    OutlineStory,
    QuestionEvidence,
)
from app.services.evidence.confidence import get_hidden_skill_names
from app.services.evidence.matching import known_canonicals
from app.services.evidence.review import dedupe_visible
from app.services.interview.kit_evidence import (
    Item,
    basis_of,
    build_items,
    competency_lines,
    evidence_is_stale,
    lists_topic,
    practice_counts,
    skill_lines,
    skill_names,
    topic_lines,
)
from app.services.interview.kit_store import get_kit
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.leetcode.leetcode_taxonomy import PRACTICE_TAGS, practice_by_skill
from app.services.resume.render import date_range

_MAX_PRACTICE_TOPICS = 5
_MAX_CLAIMS_NAMED = 3

# A figure that isn't a year.
_FIGURE = r"(?!(?:19|20)\d\d\b)\d[\d,.]*"
# A line stating how much something changed: "40%", "3x", "$2000", "by 6",
# "from 800ms to 210ms".
_OUTCOME = re.compile(
    rf"\d\s*(?:%|percent\b|x\b)|[$€£₹]\s?\d|\bby\s+{_FIGURE}"
    rf"|\bfrom\s+{_FIGURE}[^.;]{{0,30}}?\bto\s+{_FIGURE}",
    re.IGNORECASE,
)

# Where a section's facts come from.
_TITLE, _DID, _RESULT = "title", "did", "result"
_Shape = list[tuple[str, str, str | None]]  # (heading, prompt, which facts)

_WHERE = ("Situation", "Where and when this was, in a sentence or two.", _TITLE)
_STORY: _Shape = [
    _WHERE,
    ("Your task", "What you were responsible for.", None),
    ("What you did", "The steps you took yourself.", _DID),
    ("Result", "What changed because of it. Give a figure only if you know it.", _RESULT),
    ("What you learned", "What you took from it, or would do differently.", None),
]
_CONFLICT: _Shape = [
    _WHERE,
    ("The disagreement", "What the two views were, each put fairly.", None),
    ("What you did", "Your own part in settling it.", _DID),
    ("How it was settled", "How the decision was reached, and what came of it.", _RESULT),
    ("What you learned", "What you took from it.", None),
]
_FAILURE: _Shape = [
    _WHERE,
    ("What went wrong", "The problem, stated plainly, and your part in it.", None),
    ("What you did", "How you responded.", _DID),
    ("What changed afterwards", "What was fixed, and what you do differently now.", _RESULT),
]
_TECHNICAL: _Shape = [
    ("Context", "The work this comes from, in a sentence.", _TITLE),
    ("The problem", "What needed solving, and for whom.", None),
    ("What you did", "How you used it, in your own steps.", _DID),
    ("Decisions and trade-offs", "What else you could have done, and why you chose this.", None),
    ("Result", "What came of it. Give a figure only if you know it.", _RESULT),
    ("What you would change", "What you would improve with more time.", None),
]
_DESIGN: _Shape = [
    ("Context", "A system you know that raises the same questions.", _TITLE),
    ("Requirements", "What the design has to do, and the limits you would ask about.", None),
    ("How you would build it", "The main parts and how data moves between them.", _DID),
    ("Trade-offs", "What you would give up, and why.", None),
    ("What breaks first", "Where it struggles as use grows, and what you would do.", _RESULT),
]
_PRACTICE: _Shape = [
    ("What you have practised", "The kinds of problem you know best.", _DID),
    ("A problem you remember", "One you can explain from memory.", None),
    ("How you solved it", "Your approach, step by step, and why it works.", None),
    ("Its cost", "Time and memory, and what would make it cheaper.", None),
]


def _shape(question: InterviewQuestion, ref: QuestionEvidence | None) -> _Shape:
    if ref is not None and ref.kind == "leetcode_topic":
        return _PRACTICE
    if question.category == "behavioral":
        if "conflict_resolution" in question.competencies:
            return _CONFLICT
        return _FAILURE if "failure_recovery" in question.competencies else _STORY
    return _DESIGN if question.category == "system_design" else _TECHNICAL


def _outline(
    question: InterviewQuestion, ref: QuestionEvidence | None, facts: dict[str, list[OutlineFact]], **rest,
) -> AnswerOutline:
    return AnswerOutline(
        question_id=question.id,
        sections=[
            OutlineSection(heading=heading, prompt=prompt, facts=facts.get(source, []))
            for heading, prompt, source in _shape(question, ref)
        ],
        **rest,
    )


def _without_story(question: InterviewQuestion, why: str) -> AnswerOutline:
    return _outline(question, None, {}, warnings=[why])


_NOT_MATCHED = "This question hasn't been matched to your work yet. Match the kit's evidence."
_THIN = (
    "Nothing in your record answers this yet. If you have done it, add it to your profile and match the "
    "evidence again; if not, say so and describe how you would go about it."
)
_UNCHECKED = (
    "No work was matched to this question, but not all of it could be checked. Match the kit's evidence again "
    "later."
)
_GONE = "The work matched to this question has been removed or hidden. Match the kit's evidence again."
_CHANGED = "The matched work no longer shows what this question asks about. Match the kit's evidence again."


def _from_practice(question, ref: QuestionEvidence, skills: list[str], counts: dict[str, int]) -> AnswerOutline:
    if ref.skills and not skills:
        return _without_story(question, _GONE)
    tags = [ref.topic]
    for skill in skills:
        if skill in PRACTICE_TAGS:  # data structures or algorithms: several topics stand behind it
            tags += [tag for tag, _count in practice_by_skill(counts)[skill].topics]
    facts = [
        OutlineFact(text=f"{counts[tag]} problem{'' if counts[tag] == 1 else 's'} solved on LeetCode in "
                         f"{tag.replace('-', ' ')}")
        for tag in list(dict.fromkeys(tags))[:_MAX_PRACTICE_TOPICS] if counts.get(tag, 0) > 0
    ]
    if not facts:
        return _without_story(question, _GONE)
    return _outline(
        question, ref, {_DID: facts}, story=OutlineStory(kind="leetcode", title="LeetCode practice"),
        warnings=["Practice shows you can solve such problems, not that you used this at work. Say which it is."],
    )


def _claim_warning(audit: dict) -> str | None:
    if (audit.get("narrative") or {}).get("risk_level") not in ("high", "medium"):
        return None
    claims = [c for c in (audit.get("facts") or {}).get("unsupported_claims") or [] if c]
    named = f": {'; '.join(claims[:_MAX_CLAIMS_NAMED])}" if claims else ""
    return (
        f"A check of this project found claims its code doesn't support{named}. "
        "Be ready to explain them, or leave them out."
    )


def _from_work(
    question, ref: QuestionEvidence, item: Item, skills: list[str], names: dict[str, set[str]],
    technologies: list[str], audit: dict,
) -> AnswerOutline:
    basis = basis_of(question)
    warnings = []
    if basis == "skills":
        shown, relevant = skill_lines(item, skills, names)
        if not shown:
            return _without_story(question, _CHANGED if skills else _GONE)
        if not relevant:
            warnings.append(
                "No line of this work says how you used it; your record only lists it. Be ready to explain "
                "that yourself."
            )
    elif basis == "topic":
        relevant = topic_lines(item, question.topic)
        if not relevant and not lists_topic(item, question.topic):
            return _without_story(question, _CHANGED)
        if not relevant:
            warnings.append("No line of this work describes this; it is only listed among its technologies.")
    else:
        if not set(ref.competencies) & set(item.row.competency_tags or []) and item.row.competency_tags is not None:
            return _without_story(question, _CHANGED)
        relevant = competency_lines(item, ref.competencies)
        if not relevant:
            warnings.append(
                "The wording doesn't show which part of this work answers the question. Pick it from the "
                "other lines below."
            )
    if warning := _claim_warning(audit):
        warnings.append(warning)

    row, lines = item.row, item.lines
    title = f"{row.role} at {row.company}" if item.kind == "experience" else row.name
    period = (date_range(row) if item.kind == "experience" else "") or None
    url = (row.repo_url or (item.repo.html_url if item.repo else None)) if item.kind == "project" else None

    def fact(number: int) -> OutlineFact:
        return OutlineFact(text=lines[number].strip(), bullet=number)

    results = [n for n in relevant if _OUTCOME.search(lines[n])]
    if len(results) == len(relevant):  # nothing would be left to say what was done
        results = []
    return _outline(
        question, ref,
        {
            _TITLE: [OutlineFact(text=f"{title} ({period})" if period else title)],
            _DID: [fact(n) for n in relevant if n not in results],
            _RESULT: [fact(n) for n in results],
        },
        story=OutlineStory(
            kind=item.kind, id=row.id, title=title, period=period, technologies=technologies, url=url,
        ),
        other_facts=[fact(n) for n, line in enumerate(lines) if line.strip() and n not in relevant],
        warnings=warnings,
    )


async def _current_items(db: AsyncSession, user_id) -> dict:
    """row id -> each current, visible project and role."""
    rows = {}
    for kind, table in (("projects", Project), ("experiences", Experience)):
        found = await db.scalars(select(table).where(table.user_id == user_id).order_by(table.created_at.desc()))
        rows[kind] = dedupe_visible(kind, list(found))
    projects, experiences = await build_items(db, user_id, rows["projects"], rows["experiences"])
    return {item.row.id: item for item in [*projects, *experiences]}


async def answer_outlines(
    db: AsyncSession, user_id, job_intelligence_id, version: int | None = None,
) -> KitOutlines | None:
    """The outlines for a saved kit, the newest unless a version is named. None
    when the user has no such kit. No model calls, and nothing is saved.
    """
    job = await get_job_intelligence(db, user_id, job_intelligence_id)
    saved = await get_kit(db, user_id, job_intelligence_id, version)
    if job is None or saved is None:
        return None
    items = await _current_items(db, user_id)
    hidden = await get_hidden_skill_names(db, user_id)
    names = await skill_names(db, job, {skill for q in saved.questions for skill in q.skills} - hidden)
    counts = await practice_counts(db, user_id)
    audits = {
        row.project_id: row.report_json or {}
        for row in await db.scalars(
            select(ProjectClaimAuditReview).where(ProjectClaimAuditReview.user_id == user_id)
        )
    }
    canonical_of = await known_canonicals(db, {name for item in items.values() for name in item.technologies})

    def visible_technologies(item: Item) -> list[str]:
        unique: dict[str, str] = {}
        for name in item.technologies:
            canonical = canonical_of.get(name)
            if canonical not in hidden and name.strip().lower() not in hidden:
                unique.setdefault(canonical or name.strip().lower(), name.strip())
        return list(unique.values())

    def outline(question: InterviewQuestion) -> AnswerOutline:
        if not question.evidence_refs:
            if question.thin_evidence is None:
                return _without_story(question, _NOT_MATCHED)
            # A notice on the matching means some work was never tagged.
            unchecked = saved.kit.evidence_notice and basis_of(question) == "competencies"
            return _without_story(question, _UNCHECKED if unchecked else _THIN)
        ref = QuestionEvidence.model_validate(question.evidence_refs[0])
        skills = [s for s in ref.skills if s not in hidden]
        if ref.kind == "leetcode_topic":
            return _from_practice(question, ref, skills, counts)
        item = items.get(ref.id)
        if item is None:
            return _without_story(question, _GONE)
        return _from_work(
            question, ref, item, skills, names, visible_technologies(item), audits.get(ref.id, {}),
        )

    return KitOutlines(
        version=saved.kit.version,
        stale=await evidence_is_stale(db, user_id, saved.kit),
        outlines=[outline(question) for question in saved.questions],
    )
