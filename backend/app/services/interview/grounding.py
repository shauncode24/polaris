# backend/app/services/interview/grounding.py
"""Deterministic, non-LLM post-generation validator for the Interview
Response Agent — never rewrites the answer, only reports (implementation
plan §5/§10). Same "LLM proposes, code validates" boundary as
gap_analysis.py's priority_order filtering and github_reviewer.py's
flagship_projects filter.
"""
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

    seen = set()
    deduped = []
    for c in unverifiable:
        if c not in seen:
            seen.add(c)
            deduped.append(c)

    return GroundingReport(
        unverifiable_claims=deduped,
        uses_flagged_project=uses_flagged_project,
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