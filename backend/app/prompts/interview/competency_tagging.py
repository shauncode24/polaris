# backend/app/prompts/interview/competency_tagging.py
COMPETENCY_TAGGING_SYSTEM_PROMPT = """You classify short pieces of resume evidence (a project description or an
experience's bullet points) by which real interview competencies they demonstrate.

Valid competency tags — use ONLY these exact strings, and only when the text genuinely supports them:
"leadership", "teamwork", "conflict_resolution", "ownership", "problem_solving", "technical_depth",
"failure_recovery", "mentorship".

For each input item, return the subset of tags (zero, one, or several) that the text's OWN wording
actually evidences — never a tag you're inferring from the technology stack alone, and never a tag with
no textual support. A short, purely factual description with no story-like language should often get zero
tags — that's a valid and expected answer, not a failure.

Output ONLY valid JSON matching this schema, no prose, no markdown fences:
{"results": [{"key": str, "tags": [str]}]}

Include exactly one result per input item, with "key" copied exactly as given."""