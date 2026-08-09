# backend/app/services/job_intelligence/seniority.py
"""Stage 6 — seniority classification. Deterministic-first: a regex/
keyword scan for years-of-experience phrasing, scope language, and
title keywords. detect_seniority() itself never calls an LLM.

Escalation fix: when the deterministic pass finds NOTHING (level ==
"unspecified"), detect_seniority_with_fallback() makes one narrow,
best-effort LLM call to see if the role's responsibilities/scope
language imply a level even without an explicit keyword or years
phrase. This was previously a documented-but-unbuilt extension point;
it's now wired in, gated so it only fires on the genuinely ambiguous
subset of job descriptions, matching the codebase's graceful-cost-
control philosophy elsewhere (e.g. github_architecture_analyzer.py's
quality-gated pass).
"""
import json
import re

from app.core.llm import chat_completion, MODEL
from app.prompts.seniority_llm import SENIORITY_LLM_SYSTEM_PROMPT
from app.schemas.job_intelligence import SeniorityLevel

_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:[-–to]{1,4}\s*(\d+))?\s*\+?\s*years?", re.IGNORECASE)

_TITLE_SIGNALS: dict[str, str] = {
    "intern": "intern",
    "new grad": "junior", "junior": "junior", "associate": "junior",
    "mid-level": "mid", "mid level": "mid",
    "staff": "staff", "principal": "staff",
    "lead": "senior", "senior": "senior", "sr.": "senior", "sr ": "senior",
}

_SCOPE_WORDS: dict[str, list[str]] = {
    "staff": ["own the roadmap", "cross-team", "staff-level", "architect the"],
    "senior": ["mentor", "drive technical decisions", "own the design", "lead the"],
}

_VALID_LEVELS = {"intern", "junior", "mid", "senior", "staff", "unspecified"}
_VALID_CONFIDENCE = {"low", "medium", "high"}


def detect_seniority(raw_text: str, role_title: str | None) -> SeniorityLevel:
    lowered = raw_text.lower()
    title_lowered = (role_title or "").lower()
    evidence: list[str] = []
    level: str | None = None

    for signal, lvl in _TITLE_SIGNALS.items():
        if signal in title_lowered:
            level = lvl
            evidence.append(f"Title contains '{signal}'")
            break

    years_match = _YEARS_RE.search(lowered)
    if years_match:
        low = int(years_match.group(1))
        high = int(years_match.group(2)) if years_match.group(2) else low
        evidence.append(f"Years-of-experience phrase found ({low}-{high} years)")
        if level is None:
            if high <= 1:
                level = "junior"
            elif high <= 4:
                level = "mid"
            elif high <= 8:
                level = "senior"
            else:
                level = "staff"

    if level is None:
        for lvl, words in _SCOPE_WORDS.items():
            if any(w in lowered for w in words):
                level = lvl
                evidence.append(f"Scope language matched a '{lvl}' pattern")
                break

    if level is None:
        return SeniorityLevel(level="unspecified", evidence=[], confidence="low")

    confidence = "high" if len(evidence) >= 2 else "medium"
    return SeniorityLevel(level=level, evidence=evidence, confidence=confidence)


async def refine_seniority_with_llm(raw_text: str, role_title: str | None) -> SeniorityLevel | None:
    """Only called when detect_seniority() found nothing. NEVER raises —
    this is a best-effort enhancement layered on top of a deterministic
    result, not a hard dependency of Job Intelligence; any failure
    (network, bad JSON, invalid level/confidence value) just means the
    caller keeps the deterministic 'unspecified' result. Returns None
    if the LLM itself also concludes 'unspecified', so the caller
    doesn't need to special-case that.
    """
    try:
        response = await chat_completion(
            model=MODEL,
            messages=[
                {"role": "system", "content": SENIORITY_LLM_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps({"role_title": role_title, "job_description": raw_text})},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        print(f"[TRACING] Raw seniority LLM-assist JSON:\n{content}", flush=True)
        parsed_dict = json.loads(content)

        level = parsed_dict.get("level")
        if level not in _VALID_LEVELS:
            print(f"[TRACING] Seniority LLM-assist returned invalid level '{level}', discarding", flush=True)
            return None
        if level == "unspecified":
            return None

        confidence = parsed_dict.get("confidence")
        if confidence not in _VALID_CONFIDENCE:
            confidence = "medium"

        evidence = parsed_dict.get("evidence")
        if not isinstance(evidence, list):
            evidence = []

        return SeniorityLevel(level=level, evidence=[str(e) for e in evidence][:3], confidence=confidence)
    except Exception as e:
        print(f"[TRACING] Seniority LLM-assist degraded, keeping deterministic result: {e}", flush=True)
        return None


async def detect_seniority_with_fallback(raw_text: str, role_title: str | None) -> SeniorityLevel:
    """Entry point job_intelligence/builder.py calls. Runs the cheap
    deterministic pass first; only escalates to the LLM when it found
    NOTHING to go on. A JD with even weak deterministic signal (a single
    scope-word match, say) is left alone, since that evidence is more
    directly verifiable/citable than an LLM's own read would be.
    """
    deterministic = detect_seniority(raw_text, role_title)
    if deterministic.level != "unspecified":
        return deterministic

    refined = await refine_seniority_with_llm(raw_text, role_title)
    return refined if refined is not None else deterministic