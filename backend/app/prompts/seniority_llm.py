# backend/app/prompts/seniority_llm.py
"""LLM-assist escalation for seniority classification — only invoked when
the deterministic pass in seniority.py finds NO usable signal at all.
Note: even if this call gets it wrong, seniority.py's
apply_designation_override() runs on its output afterward and will
still catch an entry-level title being misclassified.
"""
SENIORITY_LLM_SYSTEM_PROMPT = """You are classifying the seniority level implied by a job description that
did NOT contain any explicit years-of-experience phrase, seniority-labeled title keyword, or clear
scope-language match on a first deterministic pass. Read the role's responsibilities, expected ownership,
and any implicit signals of scope (e.g. "own the roadmap for X" implies senior/staff; "assist the team
with Y under guidance" implies junior/intern) and decide the single best-fitting level.

CRITICAL: never treat a number describing how long the COMPANY has existed (e.g. "125+ year legacy",
"founded in 1897", "a century of trust") as a candidate-experience signal — that describes the company,
not the required years of experience for this role.

Output ONLY valid JSON matching this schema, no prose, no markdown fences:
{"level": "intern"|"junior"|"mid"|"senior"|"staff"|"unspecified", "evidence": [str], "confidence": "low"|"medium"|"high"}

Use "unspecified" ONLY if the text genuinely gives no usable signal even on a close read of responsibilities
and scope — you are allowed to reason about implicit ownership/scope language, not just explicit keywords,
so this should be rare. "evidence" must be 1-3 short, real, grounded observations from the actual text —
never invented or generic. Never fabricate a signal that isn't actually present."""