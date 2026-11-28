"""Turns skill evidence rows into the concrete things they point at: which
project, which bullet, which repo, which LeetCode topic.

Deterministic, no LLM. Callers pass rows from `get_active_skill_evidence`,
so everything returned is part of the user's current, visible record.
"""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Certificate, Experience, LeetcodeSnapshot, Project
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import SkillEvidence
from app.schemas.skill_gap.skill_gap import SupportingEvidence
from app.services.evidence.matching import known_canonicals, mentions_any, skill_aliases
from app.services.evidence.review import dedupe_visible
from app.services.evidence.scoring import decay_multiplier
from app.services.leetcode.leetcode_taxonomy import PRACTICE_TAGS, practice_by_skill

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")
# How many practised topics are listed under data structures or algorithms.
_MAX_PRACTICE_TOPICS = 5
_PRACTICE_NAMES = {"data_structures": "Data structure", "algorithms": "Algorithm"}


def _first_sentence_mentioning(text: str | None, names: set[str]) -> str | None:
    for sentence in _SENTENCE_END.split(text or ""):
        if sentence.strip() and mentions_any(sentence, names):
            return sentence.strip()
    return None


def _listed(stack: list[str] | None, names: set[str]) -> list[str]:
    return [item for item in (stack or []) if item.strip().lower() in names or mentions_any(item, names)]


def _from_project(project: Project, names: set[str]) -> SupportingEvidence:
    sentence = _first_sentence_mentioning(project.description, names)
    listed = _listed(project.stack, names)
    if sentence:
        detail = sentence
    elif listed:
        detail = f"Listed in the project's technologies ({', '.join(listed)})"
    else:
        detail = None
    return SupportingEvidence(
        kind="project", source="github" if project.source == "github" else "resume",
        title=project.name, detail=detail, item_id=str(project.id), url=project.repo_url,
    )


def _from_experience(experience: Experience, names: set[str]) -> SupportingEvidence:
    bullet = next((b for b in experience.bullets or [] if mentions_any(b, names)), None)
    listed = _listed(experience.stack, names)
    if bullet:
        detail = bullet
    elif listed:
        detail = f"Listed in the technologies for this role ({', '.join(listed)})"
    else:
        detail = None
    return SupportingEvidence(
        kind="experience", source=experience.source or "resume",
        title=f"{experience.role} at {experience.company}", detail=detail, item_id=str(experience.id),
    )


def _from_repo(analysis: GithubProjectAnalysis, project: Project | None, names: set[str]) -> SupportingEvidence:
    technologies = _listed(analysis.technologies, names)
    detail = "Detected in the repository's code and dependencies"
    if technologies:
        detail += f" ({', '.join(technologies)})"
    return SupportingEvidence(
        kind="github_repo", source="github", title=analysis.repo_name, detail=detail,
        item_id=str(project.id) if project else None, url=analysis.html_url,
    )


async def latest_leetcode_counts(db: AsyncSession, user_id) -> dict[str, int]:
    """The newest solved count stored for each LeetCode topic."""
    result = await db.execute(
        select(LeetcodeSnapshot.tag, LeetcodeSnapshot.solved_count)
        .where(LeetcodeSnapshot.user_id == user_id)
        .order_by(LeetcodeSnapshot.pulled_at.desc())
    )
    latest: dict[str, int] = {}
    for tag, count in result.all():
        latest.setdefault(tag, count)
    return latest


def _solved(title: str, count: int) -> SupportingEvidence:
    return SupportingEvidence(
        kind="leetcode_topic", source="leetcode", title=title,
        detail=f"{count} problem{'' if count == 1 else 's'} solved",
    )


def _from_practice(canonical: str, counts: dict[str, int]) -> list[SupportingEvidence]:
    """A summary of the practice behind data structures or algorithms,
    followed by the most practised topics.
    """
    topics = practice_by_skill(counts)[canonical].topics
    if not topics:
        return []
    summary = SupportingEvidence(
        kind="leetcode_topic", source="leetcode", title=f"{_PRACTICE_NAMES[canonical]} practice",
        detail=f"{len(topics)} topic{'' if len(topics) == 1 else 's'} practised on LeetCode",
    )
    return [summary] + [
        _solved(tag.replace("-", " ").capitalize(), count) for tag, count in topics[:_MAX_PRACTICE_TOPICS]
    ]


async def _leetcode_topics(db: AsyncSession, counts: dict[str, int]) -> dict[str, list[tuple[str, int]]]:
    """canonical skill -> [(LeetCode topic, problems solved)] for the topics
    that name a skill themselves.
    """
    canonical_by_tag = await known_canonicals(db, set(counts))

    topics: dict[str, list[tuple[str, int]]] = {}
    for tag, canonical in canonical_by_tag.items():
        topics.setdefault(canonical, []).append((tag, counts[tag]))
    for entries in topics.values():
        entries.sort(key=lambda t: t[1], reverse=True)
    return topics


async def build_supporting_evidence(
    db: AsyncSession, user_id, evidence_by_skill: dict[str, list[SkillEvidence]]
) -> dict[str, list[SupportingEvidence]]:
    """canonical skill -> the items backing it, strongest first. Every skill
    that has at least one evidence row gets at least one item.
    """
    if not evidence_by_skill:
        return {}

    projects = {p.id: p for p in (await db.execute(
        select(Project).where(Project.user_id == user_id)
    )).scalars().all()}
    visible_projects = dedupe_visible(
        "projects", sorted(projects.values(), key=lambda p: p.created_at, reverse=True)
    )
    project_by_repo: dict[str, Project] = {}
    for project in visible_projects:
        if project.github_repo_name:
            project_by_repo.setdefault(project.github_repo_name, project)

    experiences = {e.id: e for e in (await db.execute(
        select(Experience).where(Experience.user_id == user_id)
    )).scalars().all()}
    analyses = {a.id: a for a in (await db.execute(
        select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id)
    )).scalars().all()}
    certificates = {c.id: c for c in (await db.execute(
        select(Certificate).where(Certificate.user_id == user_id)
    )).scalars().all()}
    aliases = await skill_aliases(db, set(evidence_by_skill))
    leetcode_counts = (
        await latest_leetcode_counts(db, user_id)
        if any(r.source_type == "leetcode_tag" for rows in evidence_by_skill.values() for r in rows)
        else {}
    )
    leetcode_topics = await _leetcode_topics(db, leetcode_counts) if leetcode_counts else {}

    supporting: dict[str, list[SupportingEvidence]] = {}
    for canonical, rows in evidence_by_skill.items():
        names = aliases[canonical]
        ranked = sorted(rows, key=lambda r: r.weight * decay_multiplier(r.created_at), reverse=True)

        items: list[SupportingEvidence] = []
        for row in ranked:
            if row.source_type == "project" and row.source_id in projects:
                items.append(_from_project(projects[row.source_id], names))
            elif row.source_type == "experience" and row.source_id in experiences:
                items.append(_from_experience(experiences[row.source_id], names))
            elif row.source_type == "github_repo" and row.source_id in analyses:
                analysis = analyses[row.source_id]
                items.append(_from_repo(analysis, project_by_repo.get(analysis.repo_name), names))
            elif row.source_type == "leetcode_tag":
                if canonical in PRACTICE_TAGS:
                    found = _from_practice(canonical, leetcode_counts)
                else:
                    found = [_solved(tag, count) for tag, count in leetcode_topics.get(canonical, [])]
                items.extend(found or [SupportingEvidence(
                    kind="leetcode_topic", source="leetcode", title="LeetCode practice history",
                )])
            elif row.source_type == "linkedin_profile":
                items.append(SupportingEvidence(
                    kind="linkedin", source="linkedin", title="LinkedIn profile",
                    detail="Listed in your LinkedIn skills",
                ))
            elif row.source_type == "certificate":
                certificate = certificates.get(row.source_id)
                items.append(SupportingEvidence(
                    kind="certificate", source="certificate",
                    title=certificate.name if certificate else "Certificate",
                    detail=certificate.issuer if certificate else None,
                ))

        unique: dict[tuple, SupportingEvidence] = {}
        for item in items:
            unique.setdefault((item.kind, item.item_id, item.title), item)
        supporting[canonical] = list(unique.values())
    return supporting


_LABEL_PREFIX = {
    "project": "Project: ", "experience": "Experience: ", "github_repo": "GitHub: ",
    "leetcode_topic": "LeetCode: ", "certificate": "Certificate: ", "linkedin": "",
}


def evidence_labels(items: list[SupportingEvidence]) -> list[str]:
    """Short one-line names for the items, for prompts and summaries."""
    return list(dict.fromkeys(f"{_LABEL_PREFIX[item.kind]}{item.title}" for item in items))
