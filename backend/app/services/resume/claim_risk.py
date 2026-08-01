# backend/app/services/resume/claim_risk.py  (NEW FILE)
"""Single canonical claim-risk penalty table. Previously
projects/comparison.py penalized claim-risk projects with a flat
additive subtraction (score -= 1.0) while resume/tailoring_llm.py used
a multiplicative discount (relevance_score * (1 - 0.5)) — two
independently-tuned formulas for conceptually the same signal, despite
comments in both claiming parity with each other. Both now import from
here so a change to how much claim-risk should matter happens once.
"""

CLAIM_RISK_MULTIPLIER: dict[str, float] = {
    "high": 0.5,     # halve the score — significant unresolved risk
    "medium": 0.75,  # modest discount — partial unresolved risk
}


def apply_claim_risk_penalty(score: float, risk_level: str | None) -> float:
    multiplier = CLAIM_RISK_MULTIPLIER.get(risk_level, 1.0)
    return score * multiplier