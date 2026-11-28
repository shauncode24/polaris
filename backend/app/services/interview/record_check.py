"""Finds the figures and technologies in a piece of text that the user's record
doesn't show, without a model.

Used on a practice answer, to point out what to be sure of before saying it,
and on a model's feedback, to drop remarks that bring something in.

It compares figures and technology names only. It can't tell whether a figure
that is in the record belongs to the work being described, and says nothing
about claims made in words ("I led the team").
"""
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Certificate, Education, Experience, Project
from app.models.github_analysis import GithubProjectAnalysis
from app.models.linkedin import LinkedInProfile
from app.services.evidence.confidence import get_active_skill_evidence, get_hidden_skill_names
from app.services.evidence.matching import find_skill, known_canonicals, mentions_skill
from app.services.evidence.review import dedupe_visible
from app.services.interview.kit_evidence import practice_counts
from app.services.job_intelligence.cleanup import plain_text
from app.services.resume.skill_classifier import CANONICAL_SKILLS
from app.services.resume.sources import ORDINARY_WORDS

# Subjects and practices anyone may talk about; naming one claims no tool.
_NOT_TECHNOLOGIES = frozenset({
    "alerting", "algorithms", "api", "big_data", "concurrency", "data_modeling", "data_pipelines",
    "data_structures", "data_warehousing", "debugging", "design_patterns", "distributed_systems",
    "infrastructure_as_code", "linear_algebra", "monitoring", "multithreading",
    "object_oriented_programming", "observability", "statistics", "testing", "threat_modeling",
})
# Technologies named by ordinary words count only when written as names, away
# from the start of a sentence. "C" is left out altogether.
_WRITTEN_AS_NAMES = re.compile(
    r"(?<![.!?]\s)(?<!^)\b(Express|Go|Node|Rails|React|REST|Rust|Spark|Spring)\b(?![\w+#])"
)
_NUMBER_WORDS = {
    word: str(number) for number, word in enumerate(
        "two three four five six seven eight nine ten eleven twelve".split(), start=2,
    )
}
# A figure standing on its own, so not the 95 of "p95" or the 3 of "S3".
_FIGURE = re.compile(
    rf"(?<![\w.])(?P<number>\d+(?:[.,]\d+)*)(?P<percent>\s?(?:%|percent\b))?|\b(?P<word>{'|'.join(_NUMBER_WORDS)})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Record:
    """Everything the user's current, visible record says."""
    texts: list[str]
    skills: set[str]  # canonical names its evidence and technology lists stand for
    hidden: set[str]


@dataclass(frozen=True)
class Unrecorded:
    figures: list[str]  # as written
    technologies: list[str]

    def __bool__(self) -> bool:
        return bool(self.figures or self.technologies)


def _figures(text: str) -> list[tuple[str, str]]:
    """(what it means, as written) for each figure in the text."""
    found = []
    for match in _FIGURE.finditer(text):
        if match["word"]:
            found.append((_NUMBER_WORDS[match["word"].lower()], match[0]))
            continue
        # Commas between thousands only: "1,5" is not 15.
        number = re.sub(r",(?=\d{3}(?!\d))", "", match["number"])
        found.append((number + ("%" if match["percent"] else ""), match[0]))
    return found


def unrecorded(
    record: Record, text: str, *, also_said: str = "", given_figures: str = "",
    names: dict[str, set[str]] | None = None,
) -> Unrecorded:
    """What `text` states that neither the record nor `also_said` does. Figures
    in `given_figures` are allowed too, but not the technologies it names: a
    question about a tool gives its numbers, not experience of the tool.
    `names` (canonical -> spellings) adds technologies to those known by default.
    """
    text = plain_text(text)
    said = [plain_text(line) for line in [*record.texts, also_said] if line]
    known = {key for line in [*said, plain_text(given_figures)] for key, _shown in _figures(line)}
    figures = list(dict.fromkeys(shown for key, shown in _figures(text) if key not in known))

    spellings: dict[str, set[str]] = {}
    for spelling, canonical in CANONICAL_SKILLS.items():
        spellings.setdefault(canonical, set()).add(spelling)
    for canonical, extra in (names or {}).items():
        spellings.setdefault(canonical, set()).update(extra)

    named = {match[1] for match in _WRITTEN_AS_NAMES.finditer(text)}
    technologies: dict[str, str] = {}
    for canonical, every in spellings.items():
        if canonical in _NOT_TECHNOLOGIES:
            continue
        written = next((w for w in named if w.lower() in every), None) or next(
            (found for s in sorted(every, key=lambda s: (-len(s), s))
             if s.lower() not in ORDINARY_WORDS and (found := find_skill(text, s))), None,
        )
        if written is None:
            continue
        elsewhere = any(mentions_skill(plain_text(also_said), s) for s in every)
        in_record = canonical not in record.hidden and (
            canonical in record.skills or any(mentions_skill(plain_text(line), s)
                                              for line in record.texts for s in every)
        )
        if not (in_record or elsewhere):
            technologies[canonical] = written
    return Unrecorded(figures, sorted(technologies.values(), key=str.lower))


async def load_record(db: AsyncSession, user_id) -> Record:
    async def rows(table) -> list:
        found = await db.scalars(select(table).where(table.user_id == user_id).order_by(table.created_at.desc()))
        return list(found)

    projects = dedupe_visible("projects", await rows(Project))
    experiences = dedupe_visible("experiences", await rows(Experience))
    education = dedupe_visible("education", await rows(Education))
    repo_names = {p.github_repo_name for p in projects if p.github_repo_name}
    hidden_repos = {
        p.github_repo_name for p in await rows(Project) if p.is_hidden and p.github_repo_name
    } - repo_names
    repos = [
        a for a in await db.scalars(select(GithubProjectAnalysis).where(GithubProjectAnalysis.user_id == user_id))
        if a.repo_name not in hidden_repos
    ]
    linkedin = await db.scalar(
        select(LinkedInProfile).where(LinkedInProfile.user_id == user_id)
        .order_by(LinkedInProfile.created_at.desc()).limit(1)
    )

    texts: list = []
    technologies: list = []

    def dates(row) -> list:
        return [row.start_date_text, row.end_date_text, *(str(d) for d in (row.start_date, row.end_date) if d)]

    for e in experiences:
        texts += [e.role, e.company, *(e.bullets or []), *dates(e)]
        technologies += e.stack or []
    for p in projects:
        texts += [p.name, *(p.description or "").splitlines()]
        technologies += p.stack or []
    for school in education:
        texts += [school.institution, school.degree, school.field_of_study, *(school.details or []), *dates(school)]
    for repo in repos:
        texts += [repo.repo_name, repo.description]
        technologies += repo.technologies or []
    for certificate in await rows(Certificate):
        texts += [certificate.name, certificate.issuer]
        technologies += certificate.skills or []
    if linkedin is not None:
        technologies += (linkedin.parsed_json or {}).get("skills") or []
    texts += [f"{count} problems solved in {tag.replace('-', ' ')}"
              for tag, count in (await practice_counts(db, user_id)).items()]

    hidden = await get_hidden_skill_names(db, user_id)
    listed = await known_canonicals(db, {name for name in technologies if name})
    return Record(
        texts=[text for text in [*texts, *technologies] if text],
        skills=({*listed.values(), *await get_active_skill_evidence(db, user_id)}) - hidden,
        hidden=hidden,
    )
