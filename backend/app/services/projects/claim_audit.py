"""Deterministic claim-vs-implementation audit — for any project with a
matched GitHub repo, diff what the resume CLAIMS (stack list,
description text) against what the repo actually VERIFIES (technologies,
capabilities, architecture_assessment). Same set-difference philosophy
as resume/analysis/coverage.py's cross-source coverage check, applied at
the single-project level.

Zero LLM calls here. The LLM layer (claim_audit_llm.py) only explains
these facts in prose — it never decides whether a claim is supported.
"""
import re

_WORD_RE = re.compile(r"[a-z0-9+#.]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def audit_project_claims(
    *,
    project_name: str,
    project_stack: list[str],
    project_description: str | None,
    repo_technologies: list[str],
    repo_capabilities: list[str],
    architecture_assessment: dict | None,
    has_tests: bool | None,
    has_ci: bool | None,
    quality_score: float | None,
    activity_score: float | None,
) -> dict:
    claimed_tokens = set()
    for item in project_stack:
        claimed_tokens.add(item.strip().lower())
        claimed_tokens.update(_tokenize(item))
    claimed_tokens.update(_tokenize(project_description or ""))

    verified_tech_lower = {t.lower() for t in repo_technologies}

    # --- Unsupported claims: resume stack items the repo shows no
    # evidence of at all (loose substring check, since resume stack
    # strings and repo technology names don't always share exact
    # casing/spelling, e.g. "Postgres" vs "PostgreSQL"). ---
    unsupported_claims: list[str] = []
    for item in project_stack:
        item_lower = item.strip().lower()
        if not item_lower:
            continue
        if any(item_lower in tech or tech in item_lower for tech in verified_tech_lower):
            continue
        unsupported_claims.append(item)

    # --- Undersold work: real, verified technologies/capabilities that
    # never appear anywhere in the resume's stack or description text. ---
    undersold_work: list[str] = []
    for tech in repo_technologies:
        tech_lower = tech.lower()
        if tech_lower in claimed_tokens or any(tech_lower in t for t in claimed_tokens):
            continue
        undersold_work.append(tech)
    for cap in repo_capabilities:
        cap_tokens = _tokenize(cap)
        if cap_tokens and not (cap_tokens & claimed_tokens):
            undersold_work.append(cap)

    # --- Confirmed claims: overlap between claimed stack and verified tech ---
    confirmed_claims: list[str] = []
    for item in project_stack:
        item_lower = item.strip().lower()
        if any(item_lower in tech or tech in item_lower for tech in verified_tech_lower):
            confirmed_claims.append(item)

    architecture_flag = None
    if architecture_assessment and architecture_assessment.get("depth_label") == "flat_script":
        strong_claim_words = {"scalable", "microservices", "distributed", "architected", "production-grade"}
        if strong_claim_words & _tokenize(project_description or ""):
            architecture_flag = (
                "The resume description uses architecturally strong language, but the repo's file "
                "structure reads as a flat script with little separation of concerns."
            )

    return {
        "project_name": project_name,
        "has_repo_match": True,
        "unsupported_claims": sorted(set(unsupported_claims)),
        "undersold_work": sorted(set(undersold_work)),
        "confirmed_claims": sorted(set(confirmed_claims)),
        "architecture_flag": architecture_flag,
        "verified_facts": {
            "technologies": repo_technologies,
            "capabilities": repo_capabilities,
            "architecture_depth": architecture_assessment.get("depth_label") if architecture_assessment else None,
            "has_tests": has_tests,
            "has_ci": has_ci,
            "quality_score": quality_score,
            "activity_score": activity_score,
        },
    }