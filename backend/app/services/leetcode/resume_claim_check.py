"""Resume-claim verification against LeetCode evidence — deterministic
keyword scan (same tier-1 pattern as skill_classifier.py's
CANONICAL_SKILLS) cross-checked against real solved-problem/contest
data. The LLM never decides whether a claim is made or backed; both are
computed here as fact. See LeetCode Module Review §5.
"""
import re

CLAIM_PATTERNS: dict[str, str] = {
    r"\bcompetitive programm\w*": "competitive programmer",
    r"\bstrong (algorithmic|problem[- ]solving)\b": "strong problem-solving",
    r"\b\d{2,4}\+?\s*leetcode\b": "N+ LeetCode problems solved",
    r"\bicpc\b": "ICPC participant",
    r"\bcodeforces\b": "Codeforces participant",
    r"\bdata structures? and algorithms?\b": "DSA proficiency",
}

STRONG_TOTAL_SOLVED = 150
STRONG_CONTEST_RATING = 1600
STRONG_MASTERY_LABELS = {"Consistent Practice", "Extensive Practice"}


def _extract_claims(raw_text: str) -> list[str]:
    lowered = raw_text.lower()
    return [label for pattern, label in CLAIM_PATTERNS.items() if re.search(pattern, lowered)]


def check_resume_claims(
    raw_text: str,
    total_solved: int,
    contest_rating: float | None,
    topic_mastery: list[dict],
) -> dict:
    claims = _extract_claims(raw_text or "")
    strong_topic_count = sum(1 for t in topic_mastery if t["mastery"] in STRONG_MASTERY_LABELS)

    evidence_is_strong = (
        total_solved >= STRONG_TOTAL_SOLVED
        or (contest_rating is not None and contest_rating >= STRONG_CONTEST_RATING)
        or strong_topic_count >= 4
    )

    mismatches: list[str] = []
    opportunities: list[str] = []

    if claims and not evidence_is_strong:
        mismatches.append(
            f"Resume claims ({', '.join(claims)}) aren't yet clearly backed by LeetCode evidence "
            f"({total_solved} solved, {strong_topic_count} topics at strong mastery) — be ready for "
            f"an interviewer to test this claim directly."
        )

    if not claims and evidence_is_strong:
        opportunities.append(
            f"You have real, strong LeetCode evidence ({total_solved} solved, {strong_topic_count} "
            f"topics at strong mastery) that isn't mentioned anywhere on your resume — worth adding."
        )

    return {
        "claims_found": claims,
        "evidence_is_strong": evidence_is_strong,
        "mismatches": mismatches,
        "opportunities": opportunities,
    }