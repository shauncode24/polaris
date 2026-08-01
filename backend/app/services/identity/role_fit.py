"""Single, canonical role-fit computation — Engineering Identity fix #2.

HARD REQUIREMENT: role-fit is INTENTIONALLY, ENTIRELY LLM-generated —
there is no deterministic scoring formula anywhere in this module, and
there must never be one added back. A "sum evidence into 5 hardcoded
category buckets, divide, get a %" approach was explicitly rejected: it
can't reason about evidence depth, project quality, recency, or how
skills actually combine into real-world role readiness — all of which
genuinely change whether someone is a good "Backend Engineer" fit versus
someone who just has 3 backend keywords sitting in their evidence pool.

The LLM is given ONLY real, code-verified skill evidence (canonical
name, decayed confidence score, and real sources) — it never invents a
skill or a confidence number, only the rating and rationale.

Every caller in the codebase goes through get_role_fit() with an
explicit `scope`, instead of each reimplementing its own skill-set
construction. Previously there were THREE separate call shapes for
supposedly the same question:
  - Resume page: source-count-bucketed evidence via analyze_evidence()
  - identity_builder: decayed-confidence-bucketed evidence
  - github_reviewer: a hand-built GitHub-only pseudo-skill set, plus a
    deterministic "anchor" percentage the LLM's own rating was clamped
    against (i.e. role-fit was HALF deterministic even when an LLM was
    involved) — that clamp is removed entirely by this fix.
"""
import json

from app.core.llm import chat_completion, MODEL
from app.schemas.role_fit import RoleFitLLMOutput, RoleFitResult

VALID_ROLES = [
    "Backend Engineer", "Frontend Engineer", "Full Stack Engineer",
    "AI/ML Engineer", "DevOps / Platform",
]

ROLE_FIT_SYSTEM_PROMPT = """You are assessing a candidate's evidenced fit for five engineering role
archetypes: "Backend Engineer", "Frontend Engineer", "Full Stack Engineer", "AI/ML Engineer",
"DevOps / Platform". You are given a JSON object of real, already-verified skill evidence — each
skill's canonical name, its decayed confidence score (0-1, already computed deterministically from
real project/experience/GitHub/LeetCode/certificate evidence — you do not decide this number), and
which real sources back it. You do not invent skills, scores, or evidence not present in the input.

For each of the five roles, decide a 1-5 rating and a short, specific, evidence-grounded rationale
citing real skill names from the input. A role with almost no relevant evidenced skills should score
low (1-2); a role with several well-evidenced, clearly relevant skills should score high (4-5). Use
your own engineering judgment about which skills actually matter for each role, how they combine, and
how much weight depth vs. breadth deserves here — do NOT apply any fixed formula or percentage-overlap
rule; this is a judgment call, not arithmetic.

The input also includes a "scope" string (e.g. "all_sources", "github_only", "resume_only") — use it
only to phrase rationale honestly (e.g. "no GitHub evidence yet" vs. "no evidence anywhere"), never to
change how you weigh the roles themselves.

If the input has no skills at all, return a rating of 1 for every role with a rationale noting there's
no evidence yet for this scope.

Output ONLY valid JSON matching this schema, no prose, no markdown fences:
{"role_fit": [{"role": str, "rating": int, "rationale": str}]}

Use ONLY these five exact role name strings, one entry each: "Backend Engineer", "Frontend Engineer",
"Full Stack Engineer", "AI/ML Engineer", "DevOps / Platform"."""


class RoleFitError(Exception):
    """Raised when the role-fit LLM call fails or returns something we
    can't validate. There is deliberately NO deterministic fallback
    formula here (see module docstring) — the fallback below is an
    honestly-labeled "insufficient data" response, not a competing score.
    """


def _fallback_role_fit(reason: str) -> list[RoleFitResult]:
    return [RoleFitResult(role=r, rating=1, rationale=reason) for r in VALID_ROLES]


async def get_role_fit(skill_evidence: list[dict], scope: str) -> list[RoleFitResult]:
    """skill_evidence: [{"skill": canonical_name, "confidence": float, "sources": [str]}],
    already filtered to whatever scope the caller wants (see
    role_fit_scoping.py). This function NEVER filters or re-derives that
    evidence itself — it only reasons over what it's handed.
    """
    if not skill_evidence:
        return _fallback_role_fit(f"No verified skill evidence available yet for scope '{scope}'.")

    payload = {"scope": scope, "skills": skill_evidence}

    try:
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": ROLE_FIT_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw role-fit LLM JSON (scope={scope}):\n{content}", flush=True)
        parsed = RoleFitLLMOutput.model_validate(json.loads(content))
    except Exception as e:
        print(f"[TRACING] Role-fit LLM call degraded (scope={scope}): {e}", flush=True)
        return _fallback_role_fit("Role-fit narrative is temporarily unavailable.")

    # Never trust the LLM's role names blindly — same defensive pattern
    # used everywhere else in this codebase (gap_analysis's priority_order,
    # github_reviewer's flagship_projects filter, etc.). Note: this only
    # guards against invalid role NAMES — it never touches or clamps the
    # rating itself, since there is no deterministic ground truth to
    # clamp against anymore (that clamp is the thing this fix removes).
    by_role = {r.role: r for r in parsed.role_fit if r.role in VALID_ROLES}
    results: list[RoleFitResult] = []
    for role in VALID_ROLES:
        if role in by_role:
            r = by_role[role]
            rating = max(1, min(5, r.rating))
            results.append(RoleFitResult(role=role, rating=rating, rationale=r.rationale))
        else:
            results.append(RoleFitResult(role=role, rating=1, rationale="Not returned by the model for this scope."))
    return results