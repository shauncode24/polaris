# backend/app/prompts/seniority_llm.py
"""LLM-assist escalation for seniority classification — only invoked when
the deterministic pass in seniority.py finds NO usable signal at all
(no years-of-experience phrase, no seniority-labeled title keyword, no
scope-language match). This mirrors the "cheap deterministic pass first,
LLM only when genuinely ambiguous" pattern already documented elsewhere
in this codebase (career_planner curriculum matching, the two-tier
pattern this module's own seniority.py docstring calls out as a future
extension point). It is NOT a replacement for the deterministic pass —
JDs with even weak deterministic evidence never reach this call.
"""
SENIORITY_LLM_SYSTEM_PROMPT = """You are classifying the seniority level implied by a job description that
did NOT contain any explicit years-of-experience phrase, seniority-labeled title keyword, or clear
scope-language match on a first deterministic pass. Read the role's responsibilities, expected ownership,
and any implicit signals of scope (e.g. "own the roadmap for X" implies senior/staff; "assist the team
with Y under guidance" implies junior/intern) and decide the single best-fitting level.

Output ONLY valid JSON matching this schema, no prose, no markdown fences:
{"level": "intern"|"junior"|"mid"|"senior"|"staff"|"unspecified", "evidence": [str], "confidence": "low"|"medium"|"high"}

Use "unspecified" ONLY if the text genuinely gives no usable signal even on a close read of responsibilities
and scope — you are allowed to reason about implicit ownership/scope language, not just explicit keywords,
so this should be rare. "evidence" must be 1-3 short, real, grounded observations from the actual text —
never invented or generic. Never fabricate a signal that isn't actually present."""