"""Reading the evidence a tailored resume cites: the rows themselves, their
bullets as the resume numbers them, and how they name a skill.
"""
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Certificate, Education, Experience, Project
from app.models.github_analysis import GithubProjectAnalysis
from app.models.linkedin import LinkedInProfile
from app.schemas.resume.tailored import SourceRef
from app.services.evidence.matching import find_skill

_BULLET_MARK = re.compile(r"^\s*(?:[-*•·‣▪]|\d+[.)])\s+")
# Spellings of skills that are also ordinary words, so that finding one in a
# sentence shows nothing.
ORDINARY_WORDS = {"c", "express", "go", "node", "rails", "react", "rest", "rust", "spark", "spring"}


def description_lines(description: str | None) -> list[str]:
    """A project description holds one bullet per line."""
    return [_BULLET_MARK.sub("", line) for line in (description or "").splitlines()]


# kind of source -> its table, and the row's bullets as the resume numbers them
_SOURCES = {
    "experience": (Experience, lambda row: row.bullets or []),
    "project": (Project, lambda row: description_lines(row.description)),
    "education": (Education, lambda row: row.details or []),
    "certificate": (Certificate, lambda row: []),
    "github_repo": (GithubProjectAnalysis, lambda row: []),
    "linkedin_profile": (LinkedInProfile, lambda row: []),
}


def row_bullets(kind: str, row) -> list[str]:
    return _SOURCES[kind][1](row)


async def cited_rows(db: AsyncSession, user_id, refs: list[SourceRef]) -> dict[tuple, object]:
    """(kind, row id) -> the row, for each cited item that is the user's and not
    hidden. LeetCode practice has no rows.
    """
    rows = {}
    for kind, (table, _bullets) in _SOURCES.items():
        ids = {ref.id for ref in refs if ref.kind == kind}
        if not ids:
            continue
        query = select(table).where(table.user_id == user_id, table.id.in_(ids))
        if hasattr(table, "is_hidden"):
            query = query.where(table.is_hidden.is_(False))
        rows.update({(kind, row.id): row for row in (await db.execute(query)).scalars()})
    return rows


def _listed_names(kind: str, row, repo) -> list[str]:
    """The skills the row names one by one. `repo` is a project's repository."""
    if kind == "experience":
        return row.stack or []
    if kind == "project":
        return [*(row.stack or []), *((repo.technologies or []) if repo else [])]
    if kind == "github_repo":
        return row.technologies or []
    if kind == "certificate":
        return row.skills or []
    if kind == "linkedin_profile":
        return (row.parsed_json or {}).get("skills") or []
    return []


def stated_name(kind: str, row, spellings: set[str], repo=None) -> tuple[str, bool] | None:
    """How the row itself names a skill known by any of `spellings` (lower
    case), and whether it is in a list of skills rather than a sentence. None
    when the row doesn't name it.
    """
    for name in _listed_names(kind, row, repo):
        if name and name.strip().lower() in spellings:
            return name.strip(), True
    in_prose = sorted(spellings - ORDINARY_WORDS, key=lambda s: (-len(s), s))  # longest first
    for text in row_bullets(kind, row):
        for spelling in in_prose:
            if found := find_skill(text or "", spelling):
                return found, False
    return None
