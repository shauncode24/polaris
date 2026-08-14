# backend/app/services/interview/grounding.py
"""Deterministic, non-LLM grounding checks for the Interview Response
Agent. Two passes now exist (Phase 1):

  validate_plan()   — runs on the structured AnswerPlan, BEFORE any
                       prose exists. This is the pass that actually
                       gates something: response_generation.py rejects
                       a plan that fails this and triggers one re-plan
                       attempt before falling through to
                       insufficient_context (implementation plan §H).
  validate_answer()  — runs on the final prose, AFTER generation. Pure
                       defense-in-depth at this point (the plan it was
                       built from already passed validate_plan()), but
                       kept because prose generation could still,
                       independently, phrase something claim-flavored
                       in a way the plan didn't. Scans the FULL prose
                       text, not just the self-reported "stories_used"
                       field (Phase 0 fix).

Both share the same detection helpers (_real_story_names,
_evidence_text_blob, _flagged_project_names,
_scan_prose_for_placeholder_entities) so "what counts as real" can
never quietly drift between the two passes.
"""
import re

from app.schemas.interview.interview_response import AnswerPlan, GroundingReport, InterviewLLMOutput
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
# itself already lists as forbidden. Extend by hand if a new common
# placeholder pattern shows up in real output.
_PLACEHOLDER_LITERALS: frozenset[str] = frozenset({
    "project alpha", "innovate solutions", "stellartech", "project phoenix",
    "nova solutions", "acme corp", "acme inc", "tech innovations",
    "global solutions", "xyz corporation",
})

_GENERIC_COMPANY_SUFFIX_RE = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)\s(Solutions|Technologies|Systems|Innovations|Enterprises|Corp|Corporation)\b"
)

_PLACEHOLDER_PROJECT_RE = re.compile(r"\bProject\s+(Alpha|Beta|Phoenix|X|One|Nova)\b", re.IGNORECASE)


def _scan_prose_for_placeholder_entities(text: str, real_names: set[str]) -> list[str]:
    if not text:
        return []

    lowered = text.lower()
    real_names_lower = {n.lower() for n in real_names}
    flagged: list[str] = []

    for literal in _PLACEHOLDER_LITERALS:
        if literal in lowered and literal not in real_names_lower:
            flagged.append(literal.title())

    for match in _GENERIC_COMPANY_SUFFIX_RE.finditer(text):
        candidate = match.group(0)
        if candidate.lower() not in real_names_lower:
            flagged.append(candidate)

    for match in _PLACEHOLDER_PROJECT_RE.finditer(text):
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


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for c in items:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def validate_plan(plan: AnswerPlan, context: dict) -> GroundingReport:
    """The pass that actually gates something (implementation plan §H).
    A plan fails here whenever it cites a story or evidence source that
    isn't literally present in the real profile, or its section text
    contains a known fabricated-entity pattern. response_generation.py
    treats a non-empty unverifiable_claims/possible_fabricated_entities
    as a hard failure and triggers exactly one re-plan attempt before
    giving up and returning insufficient_context — never serving prose
    built from a plan that failed this check.
    """
    real_names = _real_story_names(context)
    evidence_blob = _evidence_text_blob(context)
    unverifiable: list[str] = []

    for story in plan.stories_used:
        if story not in real_names:
            unverifiable.append(f"story reference '{story}' not found in real profile data")

    for cite in plan.cited_evidence:
        if cite.source not in real_names:
            unverifiable.append(f"cited source '{cite.source}' not found in real profile data")

    plan_text = " ".join(
        [s.content for s in plan.sections] + [c.fact for c in plan.cited_evidence]
    )
    for match in METRIC_PATTERN.finditer(plan_text):
        number_str = match.group(0).strip()
        if number_str and number_str not in evidence_blob:
            unverifiable.append(number_str)

    flagged = _flagged_project_names(context)
    uses_flagged_project = any(story in flagged for story in plan.stories_used)

    fabricated = _scan_prose_for_placeholder_entities(plan_text, real_names)

    return GroundingReport(
        unverifiable_claims=_dedupe(unverifiable),
        uses_flagged_project=uses_flagged_project,
        possible_fabricated_entities=fabricated,
    )


def validate_answer(parsed: InterviewLLMOutput, context: dict) -> GroundingReport:
    """Post-prose defensive scan — runs after a successful prose parse
    in response_generation.py. By this point the underlying plan has
    already cleared validate_plan(), so this is purely advisory
    (nothing blocks or regenerates on it); it exists to catch a fact
    prose generation might have distorted in restyling, independent of
    what the plan itself said. Never mutates parsed.answer/answer_short.
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

    fabricated = _scan_prose_for_placeholder_entities(parsed.answer or "", real_names)

    return GroundingReport(
        unverifiable_claims=_dedupe(unverifiable),
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
    POST /interview/correct populates 'suggested_action'. Intentionally
    conservative: false negatives just mean no suggestion is shown,
    which is a safe default.
    """
    lowered = (correction or "").lower()
    return any(word in lowered for word in _OWNERSHIP_WORDS)