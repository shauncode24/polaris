"""Rewords the bullets of a tailored resume toward the job's language.

Each model call is given one bullet and the job's names for the skills that
bullet already mentions. It sees no other evidence and no other requirement,
so it has nothing to borrow a claim from. A bullet that mentions none of the
job's skills has no job language to move toward and is not sent.

A rewrite is only stored beside the original, as a pending suggestion: the
resume keeps the original wording until the user accepts it. Each one is
checked against that wording (grounding.py), which removes it or flags what
the user has to confirm.
"""
import re
from dataclasses import dataclass

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLMError, LLMReplyError, Prompt, llm_json
from app.prompts.resume.bullet_rewriting import BULLET_REWRITE_SYSTEM_PROMPT
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.schemas.resume.tailored import ResumeLine, TailoredResumeDocument
from app.services.evidence.confidence import get_hidden_skill_names
from app.services.evidence.matching import find_skill, skill_aliases
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.resume.grounding import ground_line

# A reply longer than this is not a reworded bullet.
_MAX_GROWTH = 1.5
_GROWTH_ALLOWANCE = 80  # characters; lets a very short bullet grow
_ANSWER_TOKENS = 400
# After this many bullets in a row with unusable replies, the rest are not worth
# the user's calls.
_MAX_UNUSABLE_IN_A_ROW = 3

_BULLET_MARK = re.compile(r"^(?:[-*•·‣▪]|\d+[.)])\s+")


class BulletRewrite(BaseModel):
    rewrite: str


@dataclass(frozen=True)
class RewriteResult:
    document: TailoredResumeDocument
    problem: str | None = None  # why some bullets could not be rewritten; safe to show


def _job_names(job: JobIntelligenceProfile, hidden: set[str]) -> dict[str, str]:
    """canonical skill -> the job's own wording, the user's hidden skills left out."""
    names: dict[str, str] = {}
    for skill in [*job.enriched_required_skills, *job.enriched_implicit_skills, *job.enriched_nice_to_have]:
        if skill.canonical not in hidden and skill.raw.strip():
            names.setdefault(skill.canonical, skill.raw.strip())
    return names


def _job_terms(text: str, names: dict[str, str], aliases: dict[str, set[str]]) -> list[dict]:
    """The job's skills that `text` mentions, with the spelling that showed each."""
    terms = []
    for canonical, term in names.items():
        spellings = aliases[canonical] | {term.lower()}
        # Longest first, so "REST API" is reported rather than "REST".
        for spelling in sorted(spellings, key=lambda s: (-len(s), s)):
            found = find_skill(text, spelling)
            if found:
                terms.append({"term": term, "in_bullet": found})
                break
    return terms


def _same_wording(first: str, second: str) -> bool:
    def plain(text: str) -> str:
        return " ".join(text.split()).rstrip(".").casefold()

    return plain(first) == plain(second)


async def _rewrite(bullet: str, terms: list[dict]) -> str:
    """The model's wording of `bullet` as one line. Raises an `LLMError`."""
    limit = int(len(bullet) * _MAX_GROWTH) + _GROWTH_ALLOWANCE

    def tidy(payload: dict) -> dict:
        text = payload.get("rewrite")
        if not isinstance(text, str):
            raise ValueError("'rewrite' must be text")
        text = _BULLET_MARK.sub("", " ".join(text.split()))
        if not text:
            raise ValueError("'rewrite' is empty")
        if len(text) > limit:
            raise ValueError(f"'rewrite' is longer than {limit} characters")
        return {"rewrite": text}

    reply = await llm_json(
        Prompt(BULLET_REWRITE_SYSTEM_PROMPT, {"bullet": bullet, "job_terms": terms}), BulletRewrite,
        label="resume_bullet_rewrite", expect=("rewrite",), prepare=tidy,
        temperature=0.2, max_tokens=_ANSWER_TOKENS, repair=True,
    )
    return reply.value.rewrite


async def rewrite_bullets(
    db: AsyncSession, user_id, job_intelligence_id, document: TailoredResumeDocument,
) -> RewriteResult | None:
    """A copy of `document` with a suggested rewrite on the experience and
    project bullets that mention what the job asks for. None when the user has
    no such job.

    A bullet whose reply can't be used keeps only its original wording. The
    remaining bullets are not tried once the model can't be used (including
    when the day's calls run out), or after several unusable replies in a row.
    Either way `problem` says why, and the rewrites already made are kept.
    """
    job = await get_job_intelligence(db, user_id, job_intelligence_id)
    if job is None:
        return None
    names = _job_names(job, await get_hidden_skill_names(db, user_id))
    aliases = await skill_aliases(db, set(names))

    result = document.model_copy(deep=True)
    lines: list[ResumeLine] = [
        line for entry in [*result.experience, *result.projects] for line in entry.bullets
    ]
    problem, unusable = None, 0
    for line in lines:
        original = (line.original or "").strip()
        terms = _job_terms(original, names, aliases)
        if not terms:
            continue
        try:
            rewrite = await _rewrite(original, terms)
        except LLMReplyError as e:
            problem, unusable = str(e), unusable + 1
            if unusable == _MAX_UNUSABLE_IN_A_ROW:
                break
            continue
        except LLMError as e:
            problem = str(e)
            break
        unusable = 0
        if not _same_wording(rewrite, original):
            line.rewrite, line.decision = rewrite, "pending"  # a new suggestion, not yet decided on
            ground_line(line)
    return RewriteResult(result, problem)
