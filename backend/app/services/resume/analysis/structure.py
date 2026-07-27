"""Module 1 — Structure Analyzer.

Checks which sections exist, their order, and completeness.
100% deterministic; zero LLM calls.
"""
import re

# Aliases for each logical section name.
SECTION_ALIASES: dict[str, list[str]] = {
    "contact":        ["contact", "contact information", "personal information", "personal details", "details"],
    "summary":        ["summary", "professional summary", "objective", "career objective", "about me", "profile", "about", "introduction"],
    "experience":     ["experience", "work experience", "professional experience", "employment history", "employment", "work history", "career history"],
    "education":      ["education", "academic background", "educational background", "academics", "academic qualifications"],
    "skills":         ["skills", "technical skills", "core competencies", "technologies", "tools", "tech stack", "technology stack", "key skills"],
    "projects":       ["projects", "personal projects", "side projects", "key projects", "portfolio", "selected projects"],
    "certifications": ["certifications", "certificates", "certifications & awards", "credentials", "professional certifications", "licenses"],
}

REQUIRED_SECTIONS   = {"contact", "experience", "education", "skills"}
RECOMMENDED_SECTIONS = {"summary", "projects", "certifications"}

# Ideal resume section ordering.
PREFERRED_ORDER = ["contact", "summary", "experience", "education", "projects", "skills", "certifications"]

_SECTION_HEADER_RE = re.compile(r"^.{0,60}$")  # Headers are short lines


def _detect_sections(raw_text: str) -> dict[str, int]:
    """Return {section_key: line_index} for each section found (first occurrence wins)."""
    detected: dict[str, int] = {}
    for i, line in enumerate(raw_text.split("\n")):
        stripped = line.strip().lower()
        if not stripped or len(stripped) > 55:
            continue
        for key, aliases in SECTION_ALIASES.items():
            if key in detected:
                continue
            if any(stripped == alias or stripped.rstrip(":") == alias for alias in aliases):
                detected[key] = i
                break
    return detected


def analyze_structure(raw_text: str) -> dict:
    detected = _detect_sections(raw_text)
    issues: list[dict] = []

    # Missing required sections
    for sec in REQUIRED_SECTIONS:
        if sec not in detected:
            issues.append({
                "type": "missing_required",
                "severity": "high",
                "section": sec,
                "detail": f"No '{sec.title()}' section detected — required by most ATS systems.",
            })

    # Missing recommended sections
    for sec in RECOMMENDED_SECTIONS:
        if sec not in detected:
            issues.append({
                "type": "missing_recommended",
                "severity": "medium",
                "section": sec,
                "detail": f"No '{sec.title()}' section detected — strongly recommended.",
            })

    # Section order check
    present_by_pos = sorted(
        [(sec, pos) for sec, pos in detected.items()],
        key=lambda x: x[1],
    )
    actual_order = [sec for sec, _ in present_by_pos]
    preferred_present = [s for s in PREFERRED_ORDER if s in detected]

    order_wrong: list[str] = []
    for pref_idx, sec in enumerate(preferred_present):
        actual_idx = actual_order.index(sec)
        if abs(actual_idx - pref_idx) > 1:
            order_wrong.append(sec)

    if order_wrong:
        issues.append({
            "type": "section_order",
            "severity": "low",
            "section": None,
            "detail": f"Section order could be improved. Consider moving: {', '.join(s.title() for s in order_wrong)}.",
        })

    # Score calculation
    high   = sum(1 for i in issues if i["severity"] == "high")
    medium = sum(1 for i in issues if i["severity"] == "medium")
    low    = sum(1 for i in issues if i["severity"] == "low")
    score  = max(0, 100 - high * 15 - medium * 8 - low * 3)

    return {
        "score": round(score),
        "detected_sections": list(detected.keys()),
        "missing_required":   [i["section"] for i in issues if i["type"] == "missing_required"],
        "missing_recommended":[i["section"] for i in issues if i["type"] == "missing_recommended"],
        "issues": issues,
    }
