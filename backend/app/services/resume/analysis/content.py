"""Module 4 — Content Analyzer.

Evaluates bullet quality: action verbs, passive voice, vague language,
length. Builds on the existing bullet_analysis.py primitives.
Deterministic; zero LLM calls.
"""
import re
from app.services.resume.bullet_analysis import analyze_bullet

# Strong action verbs that signal clear ownership and impact.
STRONG_ACTION_VERBS: frozenset[str] = frozenset({
    "accelerated", "achieved", "analyzed", "architected", "automated", "built",
    "collaborated", "configured", "consolidated", "contributed", "coordinated",
    "created", "debugged", "decreased", "delivered", "deployed", "designed",
    "developed", "directed", "documented", "drove", "eliminated", "engineered",
    "enhanced", "established", "executed", "expanded", "generated", "implemented",
    "improved", "increased", "initiated", "integrated", "introduced", "investigated",
    "launched", "led", "maintained", "managed", "mentored", "migrated",
    "optimized", "orchestrated", "overhauled", "pioneered", "planned", "published",
    "rebuilt", "redesigned", "reduced", "refactored", "released", "resolved",
    "restructured", "revamped", "reviewed", "saved", "scaled", "shipped",
    "spearheaded", "streamlined", "tested", "trained", "transformed", "wrote",
})

# Vague filler phrases that add no signal.
FILLER_PHRASES: tuple[str, ...] = (
    "various", "multiple", "several", "many", "a lot of",
    "team player", "go-getter", "self-starter", "dynamic", "synergy",
    "passionate about", "hardworking", "detail-oriented", "results-driven",
    "fast learner", "quick learner", "out-of-the-box", "thought leader",
)

_FIRST_WORD_RE = re.compile(r"^([A-Za-z]+)")


def _starts_with_strong_verb(text: str) -> bool:
    m = _FIRST_WORD_RE.match(text.strip())
    if not m:
        return False
    return m.group(1).lower() in STRONG_ACTION_VERBS


def _has_filler(text: str) -> bool:
    lowered = text.lower()
    return any(f in lowered for f in FILLER_PHRASES)


def analyze_content(bullets: list[str]) -> dict:
    """Analyse all bullet points collected from experience + project sections."""
    clean = [b.strip() for b in bullets if b.strip() and len(b.strip()) > 10]
    total = len(clean)

    if not total:
        return {
            "score": 0,
            "total_bullets": 0,
            "flagged_count": 0,
            "strong_verb_count": 0,
            "strong_verb_pct": 0,
            "filler_count": 0,
            "issue_type_counts": {},
            "flagged_bullets": [],
        }

    strong_verb_count = 0
    filler_count = 0
    flagged_bullets: list[dict] = []
    all_issues: list[dict] = []

    for bullet in clean:
        if _starts_with_strong_verb(bullet):
            strong_verb_count += 1
        if _has_filler(bullet):
            filler_count += 1

        issues = analyze_bullet(bullet)
        if issues:
            flagged_bullets.append({
                "text":   (bullet[:120] + "…") if len(bullet) > 120 else bullet,
                "issues": [i["type"] for i in issues],
            })
            all_issues.extend(issues)

    flagged_count = len(flagged_bullets)
    strong_verb_pct = round(strong_verb_count / total * 100)

    # Score: deduct for flagged bullets and filler usage.
    flag_penalty   = (flagged_count / total) * 55
    filler_penalty = (filler_count  / total) * 15
    score = max(0, 100 - flag_penalty - filler_penalty)

    # Aggregate issue type frequencies for the UI.
    type_counts: dict[str, int] = {}
    for issue in all_issues:
        t = issue["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "score": round(score),
        "total_bullets": total,
        "flagged_count": flagged_count,
        "strong_verb_count": strong_verb_count,
        "strong_verb_pct": strong_verb_pct,
        "filler_count": filler_count,
        "issue_type_counts": type_counts,
        "flagged_bullets": flagged_bullets[:12],  # cap for UI display
    }
