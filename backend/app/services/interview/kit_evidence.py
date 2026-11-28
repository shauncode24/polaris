"""Matches each question of an interview kit to the user's best evidence for
answering it: one project or role, or else LeetCode practice. A question with
neither is marked as having thin evidence.

What qualifies depends on what the question is about:

  skills        the item names one of them, in its technologies or its wording
  competencies  behavioral questions, and the outline's general ones: the item
                is tagged with one (see competency_tagging.py)
  topic         any other question: the item mentions the topic in those words

Among the items that qualify, one with a line showing it comes before one that
only lists it, and then the interview ranking (context_builder.score_rows)
decides, lowered for a project with unsupported claims. LeetCode practice is
used only when no project or role qualifies, and never for a behavioral
question.

Only the user's current, visible record is read; a skill they hid counts for
nothing. The only model call is the competency tagging of items not tagged
before, and without it a kit is still matched, with a notice.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.github_analysis import GithubProjectAnalysis
from app.models.interview_kit import InterviewKit
from app.schemas.interview.kit import QuestionEvidence
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.services.evidence.confidence import (
    get_active_skill_evidence,
    get_hidden_skill_names,
    get_reconciled_skill_confidences,
)
from app.services.evidence.matching import known_canonicals, mentions_any, skill_aliases
from app.services.evidence.scoring import WEAK_PRACTICE_WEIGHT, practice_weight
from app.services.evidence.state import evidence_cutoff
from app.services.evidence.supporting import latest_leetcode_counts
from app.services.interview.competency_tagging import tag_text_deterministic
from app.services.interview.context_builder import (
    load_experiences_with_tags,
    load_projects_with_tags,
    score_rows,
)
from app.services.interview.kit_outline import GENERIC_TOPICS, names_topic, spellings
from app.services.interview.kit_store import SavedKit, get_kit
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.leetcode.leetcode_taxonomy import (
    MIN_SOLVED_PER_TOPIC,
    PRACTICE_TAGS,
    practice_by_skill,
    tag_slug,
)
from app.services.resume.claim_risk import apply_claim_risk_penalty, claim_risk_by_project_id
from app.services.resume.sources import ORDINARY_WORDS, row_bullets, stated_name

_UNTAGGED = (
    "Some of your projects and roles couldn't be checked for examples of how you work, because the AI "
    "service couldn't be used. A question may show thin evidence although you have a story for it."
)


@dataclass(frozen=True)
class EvidenceMapping:
    """For each question, in order: its evidence (empty when thin)."""
    refs: list[list[QuestionEvidence]]
    mapped_at: datetime
    notice: str | None = None


@dataclass
class Item:
    """A project or role, with what is needed to tell what it shows."""
    kind: str  # "project" | "experience"
    row: object
    repo: GithubProjectAnalysis | None
    recorded: set[str]  # skills the evidence record ties to it
    skills: set[str]  # those, and the ones its technologies name
    risk: str | None = None  # unsupported claims found in a project

    @property
    def lines(self) -> list[str]:
        return [line or "" for line in row_bullets(self.kind, self.row)]

    @property
    def technologies(self) -> list[str]:
        found = [*(self.row.stack or []), *((self.repo.technologies or []) if self.repo else [])]
        return [name for name in found if name and name.strip()]


def basis_of(question) -> str:
    """What work must show to answer the question: "skills", "competencies" or
    "topic".
    """
    if question.skills:
        return "skills"
    if question.category == "behavioral" or question.topic in GENERIC_TOPICS:
        return "competencies"
    return "topic"


def _lines_where(lines: list[str], shows) -> list[int]:
    return [number for number, line in enumerate(lines) if line.strip() and shows(line)]


def skill_lines(item: Item, skills: list[str], names: dict[str, set[str]]) -> tuple[list[str], list[int]]:
    """The skills the item shows, and the numbers of its lines that mention
    one. A skill can be shown by the item's technologies alone, with no line.
    """
    matched, usable = [], set()
    for skill in skills:
        # A name that is also an ordinary word ("go") proves nothing in a
        # sentence, unless the record already ties the skill to this item.
        in_prose = names[skill] if skill in item.recorded else names[skill] - ORDINARY_WORDS
        named = stated_name(item.kind, item.row, names[skill], item.repo) is not None
        if named or any(mentions_any(line, in_prose) for line in item.lines):
            matched.append(skill)
            usable |= in_prose
    return matched, _lines_where(item.lines, lambda line: mentions_any(line, usable))


def competency_lines(item: Item, competencies: list[str]) -> list[int]:
    """The lines whose wording shows one of the competencies, by the keywords.
    Work the model tagged may have none.
    """
    wanted = set(competencies)
    return _lines_where(item.lines, lambda line: wanted & set(tag_text_deterministic(line)))


def topic_lines(item: Item, topic: str) -> list[int]:
    return _lines_where(item.lines, lambda line: names_topic(line, {topic}))


def lists_topic(item: Item, topic: str) -> bool:
    return any(names_topic(name, {topic}) for name in item.technologies)


def _shows_skills(item: Item, skills: list[str], names: dict[str, set[str]]) -> QuestionEvidence | None:
    matched, lines = skill_lines(item, skills, names)
    if not matched:
        return None
    return QuestionEvidence(kind=item.kind, id=item.row.id, skills=matched, bullet=lines[0] if lines else None)


def _shows_competencies(item: Item, competencies: list[str]) -> QuestionEvidence | None:
    matched = sorted(set(competencies) & set(item.row.competency_tags or []))
    if not matched:
        return None
    lines = competency_lines(item, competencies)
    return QuestionEvidence(kind=item.kind, id=item.row.id, competencies=matched, bullet=lines[0] if lines else None)


def _shows_topic(item: Item, topic: str) -> QuestionEvidence | None:
    lines = topic_lines(item, topic)
    if not lines and not lists_topic(item, topic):
        return None
    return QuestionEvidence(kind=item.kind, id=item.row.id, bullet=lines[0] if lines else None)


def _practice(question, skills: list[str], names: dict[str, set[str]], counts: dict[str, int]):
    """The LeetCode topic that shows the most practice of what is asked, if any
    shows enough.
    """
    if question.category == "behavioral" or not counts:
        return None
    found: list[tuple[int, str, list[str]]] = []  # (solved, tag, skills)

    def tagged(wanted: set[str], for_skills: list[str]) -> None:
        for tag in {tag_slug(name) for name in wanted}:
            if counts.get(tag, 0) >= MIN_SOLVED_PER_TOPIC:
                found.append((counts[tag], tag, for_skills))

    if basis_of(question) == "topic":
        tagged({question.topic}, [])
    for skill in skills:
        if skill in PRACTICE_TAGS:  # data structures and algorithms: judged on all their topics
            practice = practice_by_skill(counts)[skill]
            if practice_weight(practice.problems, practice.breadth) > WEAK_PRACTICE_WEIGHT:
                tag, solved = practice.topics[0]
                found.append((solved, tag, [skill]))
        else:
            tagged(names[skill], [skill])
    if not found:
        return None
    _solved, tag, shown = max(found, key=lambda entry: (entry[0], entry[1]))
    return QuestionEvidence(kind="leetcode_topic", topic=tag, skills=shown)


async def build_items(db: AsyncSession, user_id, projects: list, experiences: list) -> tuple[list[Item], list[Item]]:
    """The user's current projects and roles, in the order given."""
    repos = {a.repo_name: a for a in (await db.scalars(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)
    ))}
    skills_of: dict[tuple, set[str]] = {}
    for canonical, rows in (await get_active_skill_evidence(db, user_id)).items():
        for row in rows:
            skills_of.setdefault((row.source_type, row.source_id), set()).add(canonical)

    items = [Item("project", p, repos.get(p.github_repo_name), set(), set()) for p in projects]
    items += [Item("experience", e, None, set(), set()) for e in experiences]
    canonical_of = await known_canonicals(db, {name for item in items for name in item.technologies})
    risks = await claim_risk_by_project_id(db, [p.id for p in projects])

    for item in items:
        item.recorded = set(skills_of.get((item.kind, item.row.id), ()))
        if item.repo is not None:
            item.recorded |= skills_of.get(("github_repo", item.repo.id), set())
        listed = {canonical_of[name] for name in item.technologies if name in canonical_of}
        item.skills, item.risk = item.recorded | listed, risks.get(item.row.id)
    return items[:len(projects)], items[len(projects):]


async def skill_names(db: AsyncSession, job: JobIntelligenceProfile, canonicals: set[str]) -> dict[str, set[str]]:
    """canonical skill -> every lower-case name for it, the job's own included."""
    aliases = await skill_aliases(db, canonicals)
    names = {canonical: set(aliases[canonical]) for canonical in canonicals}
    for skill in [*job.enriched_required_skills, *job.enriched_implicit_skills, *job.enriched_nice_to_have]:
        if skill.canonical in names:
            names[skill.canonical] |= {name.lower() for name in spellings(skill, aliases)}
    return names


async def practice_counts(db: AsyncSession, user_id) -> dict[str, int]:
    """LeetCode tag -> problems solved, as of the latest sync."""
    counts: dict[str, int] = {}
    for name, count in (await latest_leetcode_counts(db, user_id)).items():
        counts[tag_slug(name)] = max(count, counts.get(tag_slug(name), 0))
    return counts


async def map_evidence(db: AsyncSession, user_id, job: JobIntelligenceProfile, questions: list) -> EvidenceMapping:
    """The best evidence for each question (anything with a category, topic,
    skills and competencies). Commits, to keep competency tags worked out on the
    way; the matching itself is not saved.
    """
    mapped_at = datetime.now(timezone.utc)  # before reading: a later change makes this out of date
    projects, experiences = await build_items(
        db, user_id, await load_projects_with_tags(db, user_id), await load_experiences_with_tags(db, user_id),
    )
    hidden = await get_hidden_skill_names(db, user_id)
    confidence = {
        canonical: entry["confidence"]
        for canonical, entry in (await get_reconciled_skill_confidences(db, user_id)).items()
    }
    counts = await practice_counts(db, user_id)
    names = await skill_names(db, job, {skill for q in questions for skill in q.skills} - hidden)

    def best(question) -> QuestionEvidence | None:
        basis = basis_of(question)
        skills = [s for s in question.skills if s not in hidden]
        found: dict = {}  # row id -> why it qualifies
        for item in [*projects, *experiences]:
            if basis == "skills":
                ref = _shows_skills(item, skills, names)
            elif basis == "competencies":
                ref = _shows_competencies(item, question.competencies)
            else:
                ref = _shows_topic(item, question.topic)
            if ref is not None:
                found[item.row.id] = ref
        if not found:
            return _practice(question, skills, names, counts)

        ranked: list[tuple[tuple, QuestionEvidence]] = []
        for group in (projects, experiences):  # recency counts within each
            scores = score_rows(
                group,
                canonicals_of=lambda i: i.skills | set(found[i.row.id].skills if i.row.id in found else ()),
                tags_of=lambda i: i.row.competency_tags,
                competency_hints=set(question.competencies),
                required_technologies=set(skills),
                confidence_by_canonical=confidence,
            )
            for item, score in zip(group, scores):
                if ref := found.get(item.row.id):
                    described = basis != "competencies" and ref.bullet is not None
                    ranked.append(((described, apply_claim_risk_penalty(score, item.risk)), ref))
        return max(ranked, key=lambda entry: entry[0])[1]

    refs = [[ref] if (ref := best(question)) else [] for question in questions]
    untagged = any(item.row.competency_tags is None for item in [*projects, *experiences])
    missed = any(not ref and basis_of(q) == "competencies" for q, ref in zip(questions, refs))
    await db.commit()
    return EvidenceMapping(refs, mapped_at, _UNTAGGED if untagged and missed else None)


async def evidence_is_stale(db: AsyncSession, user_id, kit: InterviewKit) -> bool:
    """True when the kit's questions need matching again: never matched, or the
    user's evidence has changed since.
    """
    if kit.evidence_mapped_at is None:
        return True
    cutoff = await evidence_cutoff(db, user_id)
    return cutoff is not None and kit.evidence_mapped_at < cutoff


async def remap_kit(db: AsyncSession, user_id, job_intelligence_id, version: int | None = None) -> SavedKit | None:
    """Matches a saved kit's questions against the record as it is now, keeping
    the questions themselves. None when the user has no such kit.
    """
    job = await get_job_intelligence(db, user_id, job_intelligence_id)
    saved = await get_kit(db, user_id, job_intelligence_id, version)
    if job is None or saved is None:
        return None
    mapping = await map_evidence(db, user_id, job, saved.questions)
    for question, refs in zip(saved.questions, mapping.refs):
        question.evidence_refs = [ref.model_dump(mode="json") for ref in refs]
        question.thin_evidence = not refs
    saved.kit.evidence_mapped_at, saved.kit.evidence_notice = mapping.mapped_at, mapping.notice
    await db.commit()
    return saved
