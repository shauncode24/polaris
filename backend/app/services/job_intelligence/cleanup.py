"""Deterministic clean-up of the extraction reply, applied before skills are
canonicalized.

The prompt asks for all of this too; these rules are the backstop, because a
skill entry that bundles several things ("C/C++"), names a personal trait, or
rests on a quote that isn't in the posting can never be matched against a
user's evidence and shows up as a false gap.
"""
import re
import unicodedata

from app.schemas.job_intelligence.job_intelligence import (
    EnrichedSkill,
    ExtractedImplicitSkill,
    ExtractedSkillRequirement,
)

_DASHES = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_QUOTES = {ord("‘"): "'", ord("’"): "'", ord("“"): '"', ord("”"): '"'}

# Phrases that name two skills without a separator that is safe to split on.
_COMPOUNDS = {
    "data structures and algorithms": ["Data structures", "Algorithms"],
    "data structures & algorithms": ["Data structures", "Algorithms"],
    "dsa": ["Data structures", "Algorithms"],
    "monitoring and alerting": ["Monitoring", "Alerting"],
    "testing and debugging": ["Testing", "Debugging"],
    "ruby on rails": ["Ruby on Rails"],
}
# Terms whose slash is part of the name.
_SLASH_NAMES = re.compile(r"(?<![a-z])(ci/cd|a/b|tcp/ip|pl/sql|ui/ux|ux/ui|i/o)(?![a-z])", re.IGNORECASE)
_QUALIFIERS = {
    "preferred", "optional", "plus", "a plus", "mandatory", "required", "basic", "basics",
    "intermediate", "advanced",
}
_EXAMPLE_LEAD = re.compile(r"^(?:e\.g\.?|eg\.?|such as|like|including)[\s,:]*", re.IGNORECASE)
_PARENTHESES = re.compile(r"^(?P<head>[^()]*?)\s*\((?P<inner>[^()]*)\)\s*(?P<tail>[^()]*)$")

_TRAIT = (
    r"(?:analytical|logical|critical|problem[\s-]?solving|communication|interpersonal|collaboration|"
    r"teamwork|team[\s-]player|leadership|ownership|time management|attention to detail|"
    r"self[\s-]starter|systems thinking)"
)
_FILLER = r"(?:strong|excellent|good|great|effective|clear|written|verbal|oral|and|or|&)"
_SOFT_SKILL = re.compile(
    rf"^(?:{_FILLER}[\s,]+)*{_TRAIT}"
    rf"(?:(?:\s*[,&]\s*|\s+)(?:{_TRAIT}|{_FILLER}|thinking|skills?|abilit(?:y|ies)|mindset))*$",
    re.IGNORECASE,
)


# A duty's verb on its own ("Deploy"). The noun ("Testing", "Design patterns") is a skill.
_BARE_VERBS = {"build", "debug", "deploy", "design", "develop", "implement", "improve", "maintain", "test"}
# Things a posting asks for that are a history, not a skill.
_BACKGROUND = re.compile(
    r"open[\s-]?source contributions?|(?:side|github) projects?|(?:industry|company|domain|research) experience$",
    re.IGNORECASE,
)


def plain_text(value: str) -> str:
    """Folds typographic variants (non-breaking hyphens, curly quotes, odd
    spaces) so the same words compare equal.
    """
    folded = unicodedata.normalize("NFKC", value).translate(_DASHES).translate(_QUOTES)
    return re.sub(r"\s+", " ", folded).strip()


def _short(parts: list[str]) -> bool:
    return all(part and len(part.split()) <= 3 for part in parts)


def split_skill(name: str) -> list[str]:
    """The individual skills named by one extracted entry.

    "AWS (S3, EKS)" -> AWS, S3, EKS. A single item in parentheses is a
    clarification ("Linux (Ubuntu)") and is dropped, leaving the skill itself.
    """
    name = plain_text(name).strip(" .;:,")
    if not name:
        return []
    if name.lower() in _COMPOUNDS:
        return list(_COMPOUNDS[name.lower()])

    bracketed = _PARENTHESES.match(name)
    if bracketed:
        head = f"{bracketed['head']} {bracketed['tail']}".strip()
        inner = [
            _EXAMPLE_LEAD.sub("", part).strip()
            for part in re.split(r"\s*(?:,|/|\band\b|\bor\b)\s*", bracketed["inner"])
        ]
        inner = [part for part in inner if part and part.lower() not in _QUALIFIERS]
        if not head:
            return [skill for part in inner for skill in split_skill(part)]
        extra = inner if len(inner) > 1 else []
        return split_skill(head) + [skill for part in extra for skill in split_skill(part)]

    if "," in name or re.search(r"\sor\s", name):
        parts = [p.strip() for p in re.split(r"\s*(?:,|\bor\b|\band\b)\s*", name) if p.strip()]
        if len(parts) > 1 and _short(parts):
            return [skill for part in parts for skill in split_skill(part)]

    if "/" in name and not _SLASH_NAMES.search(name):
        parts = [p.strip() for p in name.split("/")]
        if len(parts) > 1 and _short(parts):
            return [skill for part in parts for skill in split_skill(part)]

    return [name]


def is_soft_skill(name: str) -> bool:
    return _SOFT_SKILL.match(plain_text(name)) is not None


def is_not_a_skill(name: str) -> bool:
    """A personal trait, a bare verb, or a piece of the candidate's history."""
    name = plain_text(name)
    return is_soft_skill(name) or name.lower() in _BARE_VERBS or _BACKGROUND.search(name) is not None


def _technical_parts(name: str) -> list[str]:
    if is_not_a_skill(name):
        return []
    return [part for part in split_skill(name) if not is_not_a_skill(part)]


def clean_requirements(items: list[ExtractedSkillRequirement]) -> list[ExtractedSkillRequirement]:
    return [item.model_copy(update={"skill": part}) for item in items for part in _technical_parts(item.skill)]


def _comparable(value: str) -> str:
    return plain_text(value).lower().strip(" .;:,\"'-")


def clean_implicit(items: list[ExtractedImplicitSkill], source_text: str) -> list[ExtractedImplicitSkill]:
    """An inferred skill is kept only if the phrase it was inferred from really
    is in the posting. Without that there is nothing to show the user.
    """
    source = plain_text(source_text).lower()
    kept: list[ExtractedImplicitSkill] = []
    for item in items:
        quote = _comparable(item.evidence)
        if not quote or quote not in source:
            continue
        kept.extend(item.model_copy(update={"skill": part}) for part in _technical_parts(item.skill))
    return kept


def drop_repeats(
    required: list[EnrichedSkill], implicit: list[EnrichedSkill], nice_to_have: list[EnrichedSkill]
) -> tuple[list[EnrichedSkill], list[EnrichedSkill]]:
    """A skill belongs to one band. What the posting states outright beats an
    inference, and "required" beats "nice to have". Returns the implicit and
    nice-to-have lists without the repeats.
    """
    taken = {s.canonical for s in required}
    nice = [s for s in nice_to_have if s.canonical not in taken]
    taken |= {s.canonical for s in nice}
    return [s for s in implicit if s.canonical not in taken], nice
