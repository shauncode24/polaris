# backend/app/services/interview/grounding.py
"""Deterministic, non-LLM post-generation validator for the Interview
Response Agent — never rewrites the answer, only reports (implementation
plan §5/§10). Same "LLM proposes, code validates" boundary as
gap_analysis.py's priority_order filtering and github_reviewer.py's
flagship_projects filter.

Phase 0 extension (plan §H): previously this only checked the model's
own self-reported "stories_used" field for real names and did a naive
substring search for numeric claims. Neither scanned the ANSWER PROSE
itself for a fabricated entity name the model might invent without
ever declaring it in stories_used. This module now additionally scans
the full prose for the specific, common hallucination pattern the
prompt already explicitly forbids by name (generic placeholder project/
company names like "Project Alpha", "Innovate Solutions") — the same
hand-seeded pattern-list philosophy leetcode_reviewer.py already uses
for _flag_ungrounded_company_mentions. This is deliberately NOT
general-purpose named-entity verification (that needs real NER, out of
scope for Phase 0) — it catches the concrete failure mode without
flagging a real, legitimately-named project.
"""
import re

from app.schemas.interview.interview_response import GroundingReport, InterviewLLMOutput
from app.services.resume.analysis.shared_signals import METRIC_PATTERN


def _real_story_names(context: dict) -> set[str]:
    """Every real, literal name the model was allowed to cite as a
    'story used' — project names, "{role} at {company}" experience
    labels, and github repo names. Built fresh from the same profile
    dict handed to the LLM, so this can never drift from what was
    actually real input.
    """
    profile = context.get("profile", {})
    names: set[str] = set()
    for p in profile.get("projects", []):
        if p.get("name"):
            names.add(p["name"])
    for e in profile.get("experiences", []):
        if e.get("label"):
            names.add(e["label"])
        if e.get("role") and e.get("company"):
            names.add(f"{e['role']} at {e['company']}")
        if e.get("company"):
            names.add(e["company"])
    for r in profile.get("github_repos", []):
        if r.get("name"):
            names.add(r["name"])
    return names


def _evidence_text_blob(context: dict) -> str:
    """Concatenation of every real text/number field the model could
    have drawn a genuine numeric claim from — bullets, descriptions,
    LeetCode/GitHub stats — used only as a substring search corpus for
    numeric-claim verification, never parsed structurally.
    """
    profile = context.get("profile", {})
    parts: list[str] = []
    for p in profile.get("projects", []):
        parts.append(p.get("description") or "")
    for e in profile.get("experiences", []):
        parts.extend(e.get("bullets") or [])
    for edu in profile.get("education", []):
        parts.extend(edu.get("details") or [])
    for r in profile.get("github_repos", []):
        parts.append(str(r.get("quality_score", "")))
        parts.append(str(r.get("activity_score", "")))
        parts.append(str(r.get("commit_hygiene_score", "")))
    lc = profile.get("leetcode_evidence") or {}
    for key in ("total_solved", "easy", "medium", "hard"):
        if lc.get(key) is not None:
            parts.append(str(lc[key]))
    return " ".join(parts)


def _flagged_project_names(context: dict) -> set[str]:
    identity = context.get("identity") or {}
    return {
        d.get("project") for d in identity.get("claim_risk_details", []) if d.get("project")
    }


# Hand-seeded literal placeholder names — exactly the ones the prompt
# itself already lists as forbidden (see interview_response.py's "DO
# NOT use generic or placeholder names" instruction). Extend by hand if
# a new common placeholder pattern shows up in real output.
_PLACEHOLDER_LITERALS: frozenset[str] = frozenset({
    "project alpha", "innovate solutions", "stellartech", "project phoenix",
    "nova solutions", "acme corp", "acme inc", "tech innovations",
    "global solutions", "xyz corporation",
})

# Generic "<Capitalized Word(s)> Solutions/Technologies/..." pattern —
# the most common shape of an invented company name. Cross-checked
# against real_names before flagging so a genuinely real company that
# happens to end in one of these words is never flagged.
_GENERIC_COMPANY_SUFFIX_RE = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)\s(Solutions|Technologies|Systems|Innovations|Enterprises|Corp|Corporation)\b"
)

_PLACEHOLDER_PROJECT_RE = re.compile(r"\bProject\s+(Alpha|Beta|Phoenix|X|One|Nova)\b", re.IGNORECASE)


def _scan_prose_for_placeholder_entities(answer: str, real_names: set[str]) -> list[str]:
    if not answer:
        return []

    lowered = answer.lower()
    real_names_lower = {n.lower() for n in real_names}
    flagged: list[str] = []

    for literal in _PLACEHOLDER_LITERALS:
        if literal in lowered and literal not in real_names_lower:
            flagged.append(literal.title())

    for match in _GENERIC_COMPANY_SUFFIX_RE.finditer(answer):
        candidate = match.group(0)
        if candidate.lower() not in real_names_lower:
            flagged.append(candidate)

    for match in _PLACEHOLDER_PROJECT_RE.finditer(answer):
        candidate = match.group(0)
        if candidate.lower() not in real_names_lower:
            flagged.append(candidate)

    seen: set[str] = set()
    deduped: list[str] = []
    for f in flagged:
        if f.lower() not in seen:
            seen.add(f.lower())
            deduped.append(f)
    return deduped


def validate_answer(parsed: InterviewLLMOutput, context: dict) -> GroundingReport:
    """Runs after a successful parse in response_generation.py. Purely
    additive — never mutates parsed.answer/answer_short.
    """
    unverifiable: list[str] = []

    evidence_blob = _evidence_text_blob(context)
    for match in METRIC_PATTERN.finditer(parsed.answer or ""):
        number_str = match.group(0).strip()
        if number_str and number_str not in evidence_blob:
            unverifiable.append(number_str)

    real_names = _real_story_names(context)
    for story in parsed.stories_used:
        if story not in real_names:
            unverifiable.append(f"story reference '{story}' not found in real profile data")

    flagged = _flagged_project_names(context)
    uses_flagged_project = any(story in flagged for story in parsed.stories_used)

    # NEW — full-prose scan (Phase 0, plan §H), independent of what the
    # model self-reported in stories_used.
    fabricated = _scan_prose_for_placeholder_entities(parsed.answer or "", real_names)

    seen = set()
    deduped = []
    for c in unverifiable:
        if c not in seen:
            seen.add(c)
            deduped.append(c)

    return GroundingReport(
        unverifiable_claims=deduped,
        uses_flagged_project=uses_flagged_project,
        possible_fabricated_entities=fabricated,
    )


_OWNERSHIP_WORDS = [
    "led", "lead", "sole", "solely", "alone", "single-handedly", "owned",
    "responsible for", "in charge of", "spearheaded", "one of", "team of",
    "co-", "with a team", "with the team",
]


def looks_like_durable_correction(correction: str) -> bool:
    """Heuristic (deterministic, no LLM) for whether a correction reads
    like it's fixing a durable fact (role/ownership/scope language) as
    opposed to a purely stylistic nit. Used to decide whether
    POST /interview/correct populates 'suggested_action' — see
    implementation plan §13. Intentionally conservative: false negatives
    just mean no suggestion is shown, which is a safe default.
    """
    lowered = (correction or "").lower()
    return any(word in lowered for word in _OWNERSHIP_WORDS)