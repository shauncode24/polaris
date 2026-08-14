# backend/app/services/interview/golden_set.py
"""The Phase 3 golden question set, per implementation plan §Q — pulled
forward as data so a minimal, hand-runnable smoke test (see
eval_harness.py) can exist BEFORE the full CI harness. Each entry names
what the classifier SHOULD produce; "expected_story_hint"/
"forbidden_substrings" are optional, per-run overrides a caller can
supply for a specific known test user — left empty here since this
module is user-independent, generic data, not a fixture tied to one
account. Extend by hand as new question phrasings show up that the
classifier gets wrong in practice — same "cheap and explainable"
philosophy as skill_categories.py / github_taxonomy.py elsewhere in
this codebase.
"""

GOLDEN_QUESTIONS: list[dict] = [
    {"id": "g01", "question": "Tell me about yourself.", "expected_blueprint": "tell_me_about_yourself"},
    {"id": "g02", "question": "Why should we hire you?", "expected_blueprint": "why_hire_you"},
    {"id": "g03", "question": "Why are you interested in this role?", "expected_blueprint": "why_this_role"},
    {"id": "g04", "question": "Why do you want to work at our company specifically?", "expected_blueprint": "why_this_company"},
    {"id": "g05", "question": "What's your biggest weakness?", "expected_blueprint": "biggest_weakness"},
    {"id": "g06", "question": "What's your greatest strength?", "expected_blueprint": "biggest_strength"},
    {"id": "g07", "question": "Tell me about a project you're really proud of.", "expected_blueprint": "proud_project"},
    {"id": "g08", "question": "Describe a time you faced a really difficult technical challenge.", "expected_blueprint": "challenge"},
    {"id": "g09", "question": "Tell me about a time you failed at something.", "expected_blueprint": "failure"},
    {"id": "g10", "question": "Tell me about a time you led a team or project.", "expected_blueprint": "leadership"},
    {"id": "g11", "question": "Describe a time you had a disagreement with a teammate.", "expected_blueprint": "conflict"},
    {"id": "g12", "question": "Tell me about a mistake you made and how you handled it.", "expected_blueprint": "mistake"},
    {"id": "g13", "question": "Where do you see yourself in five years?", "expected_blueprint": "career_goals"},
    {"id": "g14", "question": "Walk me through your resume.", "expected_blueprint": "walk_through_resume"},
    {"id": "g15", "question": "Do you have any questions for us?", "expected_blueprint": "questions_for_us"},
    {"id": "g16", "question": "Tell me about something you fully owned end-to-end.", "expected_blueprint": "ownership"},
    {"id": "g17", "question": "What did you actually do during your internship?", "expected_blueprint": "internship"},
    {"id": "g18", "question": "Explain one of your projects in technical depth — architecture, trade-offs, all of it.", "expected_blueprint": "explain_project"},
    # Continuity-specific two-turn case — run as a pair against the same
    # session_id, second question depends on the first's answer existing.
    {"id": "g19a", "question": "Tell me about the hardest bug you ever had to fix.", "expected_blueprint": "challenge", "continuity_setup": True},
    {"id": "g19b", "question": "What was the hardest part of that?", "expected_blueprint": "challenge", "continuity_followup_to": "g19a"},
    # Injected-hallucination-bait phrasing — a genuinely-worded question
    # that offers no easy real evidence, to see whether the pipeline
    # invents a story rather than admitting insufficient_context or
    # picking something honestly thin.
    {"id": "g20", "question": "Tell me about a time you built a distributed system handling millions of requests per second.", "expected_blueprint": "technical_default"},
]