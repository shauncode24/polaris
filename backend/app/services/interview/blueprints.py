# backend/app/services/interview/blueprints.py
"""Deterministic library of interview-answer blueprints — hand-curated
structural scaffolding for interview question types, based on how real
interview coaches teach candidates to structure answers.

This is DATA, not decision logic. The LLM still decides everything about
content: which blueprint (if any) actually fits the real question in
front of it, which stories/evidence fill each section, what competencies
apply, and how every sentence is phrased. This module never selects a
blueprint for a given question — it only stores the finite set of
options and hands the whole library to the model as reference material,
the same way skill_categories.py hands CATEGORY_MAP to code as a stable
vocabulary rather than deriving it fresh every time.

Each blueprint names WHAT KIND OF SECTION comes in what order and WHY
(objective) — never literal sentences. The model fills every section
with real evidence, in its own words, in the tone described by PERSONA.
"""

BLUEPRINTS: dict[str, dict] = {
    "tell_me_about_yourself": {
        "objective": "Introduce yourself and create a strong first impression, as a short personal story with a beginning, middle, and end — not a project summary.",
        "target_length": "roughly 180-260 words, spoken",
        "sections": [
            "Present — who you are right now (year/program/current status)",
            "Journey — how you got into this field, grounded ONLY in real evidence, never an invented lifelong passion",
            "2-3 strongest experiences in chronological order, each connected to the next with a real bridge sentence about what it led to or taught you",
            "What ties them together — the real common thread across those experiences",
            "Close — what you're looking for next and why you're in this conversation",
        ],
        "notes": [
            "Weight real professional/internship experience as generally more credible for this question than solo hackathon/personal projects — but use judgment on the specific profile rather than following this rigidly.",
            "Do not lead with technology names or acronyms. Say what was built/solved in plain terms first; name specific technologies only afterward, as supporting detail.",
            "Never claim a lifelong fascination or passion unless the profile evidence genuinely supports it — ground interest formation in specific real experiences instead (a hackathon, an internship, a course).",
        ],
    },
    "why_hire_you": {
        "objective": "Make a clear case for your value — a point of view backed by evidence, not a list of adjectives.",
        "sections": [
            "Your strongest, most relevant strength, stated directly",
            "Real evidence backing it",
            "A second strength",
            "Real evidence backing that",
            "Tie both directly to the target role/company if known, or to the kind of work you want",
        ],
        "notes": ["Never state a strength without immediately proving it with something real."],
    },
    "why_this_role": {
        "objective": "Explain genuine role fit.",
        "sections": [
            "What genuinely excites you about this kind of work",
            "The real experience that connects to it",
            "How your actual skills match what the role needs",
            "What you hope to grow into",
        ],
        "notes": ["Ground excitement in something specific, not generic enthusiasm."],
    },
    "why_this_company": {
        "objective": "Explain genuine company fit — only answerable if real company context exists.",
        "sections": [
            "Something specific about the company from the provided company notes",
            "The real experience that connects to that",
            "What you could contribute",
            "What you'd want to learn there",
        ],
        "notes": ["If no real company-specific information was provided, flag insufficient_context instead of answering generically."],
    },
    "why_leaving": {
        "objective": "Explain a transition positively, without complaining.",
        "sections": ["A positive framing", "What you're growing toward", "How the new opportunity aligns", "Genuine excitement about what's next"],
        "notes": ["Never frame this as a complaint about a previous employer/team."],
    },
    "biggest_weakness": {
        "objective": "Show real self-awareness, not a disguised strength.",
        "sections": [
            "One genuine weakness, stated plainly",
            "A specific real moment it affected you",
            "The concrete action you're actually taking about it",
            "Where you genuinely stand with it now",
        ],
        "notes": ["Never use a disguised-strength weakness like 'I'm a perfectionist' with no substance."],
    },
    "biggest_strength": {
        "objective": "State and prove your strongest quality.",
        "sections": ["The strength, stated directly", "Real evidence", "The real impact it had", "Why it matters for the work you want"],
        "notes": [],
    },
    "proud_project": {
        "objective": "Tell a focused technical story — problem/solution shape, not a tech-stack recitation.",
        "sections": [
            "Situation — the real problem, in plain terms first",
            "Task — what specifically you set out to do",
            "Action — what you built/decided, naming technologies as supporting detail, not the headline",
            "Challenges — a real obstacle",
            "Result — the concrete outcome (use a real number from the profile if one genuinely exists)",
            "Learning — what it taught you",
        ],
        "notes": ["Do not open with a list of technologies — open with the problem being solved."],
    },
    "challenge": {
        "objective": "Tell a real story about handling a hard problem.",
        "sections": ["The challenge/constraint", "The actions you took", "The result", "What you learned — required, never omit"],
        "notes": [],
    },
    "failure": {
        "objective": "Show accountability and growth from a real failure.",
        "sections": ["The failure, stated plainly", "Your own responsibility — no blaming others", "How you responded", "What you learned", "How you apply that now"],
        "notes": ["Never blame teammates or circumstances as the primary cause."],
    },
    "leadership": {
        "objective": "Show real leadership — doesn't require a formal title.",
        "sections": ["The situation and your responsibility", "A real decision you made", "How you coordinated with others", "The concrete result", "What you learned about leading"],
        "notes": ["Leadership can mean owning a module or driving a hackathon, not just being a manager."],
    },
    "teamwork": {
        "objective": "Show real collaboration, focused on communication.",
        "sections": ["The shared goal", "A real difference of opinion that came up", "How it was communicated/resolved", "The result"],
        "notes": [],
    },
    "conflict": {
        "objective": "Show mature conflict handling.",
        "sections": ["The real disagreement", "How you understood the other side", "The discussion/resolution", "How the relationship was afterward"],
        "notes": ["Never frame the other person as simply wrong."],
    },
    "mistake": {
        "objective": "Show ownership of a real mistake.",
        "sections": ["The mistake", "Its real impact", "How you took ownership", "How you corrected it", "What you changed to prevent it recurring"],
        "notes": [],
    },
    "career_goals": {
        "objective": "Explain a coherent trajectory.",
        "sections": ["Short-term goal", "Medium-term goal", "Long-term direction", "How this specific opportunity helps get there"],
        "notes": [],
    },
    "three_words": {
        "objective": "Give three real, evidenced traits.",
        "sections": ["Trait one + real evidence", "Trait two + real evidence", "Trait three + real evidence"],
        "notes": ["Every trait needs a specific real example — no bare adjectives."],
    },
    "motivation": {
        "objective": "Explain what genuinely drives you at work.",
        "sections": ["The real motivation", "A specific example of it showing up", "How it connects to the role/company"],
        "notes": [],
    },
    "looking_for": {
        "objective": "Describe what you want from a role, honestly and specifically.",
        "sections": ["What you want to keep learning", "How much ownership you're looking for", "The kind of impact you want", "The kind of team you work best in"],
        "notes": [],
    },
    "why_software": {
        "objective": "Explain a genuine path into software.",
        "sections": ["How it started", "How the interest developed", "The real projects that deepened it", "What you're focused on now"],
        "notes": [],
    },
    "why_ai": {
        "objective": "Explain a genuine path into AI specifically.",
        "sections": ["What first drew you in", "The first real exposure/project", "How later projects built on that", "Where you want to take it next"],
        "notes": [],
    },
    "explain_project": {
        "objective": "Walk through one project in technical depth.",
        "sections": ["The real problem and who it was for", "Its users", "How it was architected", "A real challenge faced", "The outcome", "What you'd improve given more time"],
        "notes": [],
    },
    "walk_through_resume": {
        "objective": "A chronological, factual walk through background — more sequential and less narrative than 'tell me about yourself'.",
        "sections": ["Education", "Internship/professional experience", "Key projects", "Core skills", "Current focus"],
        "notes": ["Keep this more matter-of-fact than the personal-story shape of 'tell me about yourself'."],
    },
    "not_on_resume": {
        "objective": "Reveal something real and human not captured by the formal profile.",
        "sections": ["A genuine personal quality or interest", "A real example of it", "What it taught you", "How it connects to how you work"],
        "notes": ["Don't force this into a STAR shape — it's meant to be lighter and more personal."],
    },
    "questions_for_us": {
        "objective": "Show genuine curiosity about the role/team — never decline to ask anything.",
        "sections": ["A question about the role", "A question about the team", "A question about engineering practices", "A question about growth", "A question about what success looks like"],
        "notes": ["Never answer with 'no, I don't have any questions.'"],
    },
    "ownership": {
        "objective": "Show genuine end-to-end ownership of something real — not just contribution, but being the person accountable for it.",
        "sections": [
            "The real thing you owned and its scope",
            "A concrete decision you made unprompted, without being told what to do",
            "How you handled the parts nobody else was covering",
            "The real outcome",
            "What owning it taught you about responsibility",
        ],
        "notes": [
            "Ownership can be a feature, a service, a process, or a project — it doesn't require a title.",
            "Never claim ownership of something a team collectively drove without a real individual thread to point to.",
        ],
    },
    "internship": {
        "objective": "Talk about an internship/early experience honestly — what you actually did, and what you genuinely learned, without inflating scope.",
        "sections": [
            "The real team/context you were placed in",
            "What you were actually asked to do first",
            "How your scope grew (if it genuinely did) over the internship",
            "A real contribution, sized honestly for an internship",
            "What you took away that changed how you work now",
        ],
        "notes": [
            "Never inflate an internship task into a headline ownership claim it wasn't.",
            "It's fine, and often more credible, to describe a bounded, well-executed task rather than claiming broad scope.",
        ],
    },
    # Generic fallbacks for questions that don't cleanly match anything above.
    "behavioral_default": {
        "objective": "Generic behavioral story structure.",
        "sections": ["Situation", "Task", "Action", "Result", "Reflection — what you learned"],
        "notes": [],
    },
    "technical_default": {
        "objective": "Generic technical explanation structure.",
        "sections": ["Problem", "Approach", "Architecture/decisions", "Challenges", "Result", "Learning"],
        "notes": [],
    },
    "motivation_default": {
        "objective": "Generic motivation/why-question structure.",
        "sections": ["Interest", "Evidence", "Alignment with the role/company", "Future"],
        "notes": [],
    },
}


PERSONA: dict = {
    "role_stage": "early-career engineer / student — not a senior executive, not a marketing team",
    "speaking_style": {
        "formal": False,
        "uses_contractions": True,
        "first_person": True,
        "avoids_corporate_jargon": True,
        "avoids_buzzwords": [
            "leverage", "leveraging", "actionable insights", "diverse applications",
            "cutting-edge", "synergy", "passionate", "highly motivated",
            "truly intelligent", "boundaries of AI",
        ],
        "leads_with_plain_language_before_technical_terms": True,
        "uses_natural_transitions_between_experiences": True,
        "never_invents_unevidenced_motivations": True,
        "varies_sentence_length": True,
    },
}


# Maps a blueprint key to the interview-competency tags (see
# services/interview/competency_tagging.py) most relevant to that
# question shape — used by context_builder.py's retrieval layer to RANK
# evidence, never to filter anything out entirely. A blueprint with no
# entry here (e.g. "questions_for_us", which needs no personal story)
# simply gets no competency bonus during ranking — that's a correct
# no-op, not a missing case that needs handling.
BLUEPRINT_COMPETENCY_HINTS: dict[str, list[str]] = {
    "leadership": ["leadership", "ownership"],
    "teamwork": ["teamwork", "conflict_resolution"],
    "conflict": ["conflict_resolution", "teamwork"],
    "challenge": ["problem_solving", "ownership"],
    "failure": ["failure_recovery", "ownership"],
    "mistake": ["failure_recovery", "ownership"],
    "proud_project": ["technical_depth", "ownership"],
    "explain_project": ["technical_depth"],
    "biggest_weakness": ["failure_recovery"],
    "biggest_strength": ["ownership", "technical_depth"],
    "ownership": ["ownership", "leadership"],
    "internship": ["mentorship", "teamwork"],
    "not_on_resume": ["mentorship", "teamwork"],
    "technical_default": ["technical_depth", "problem_solving"],
    "behavioral_default": ["ownership", "problem_solving"],
}


def get_blueprint_library() -> dict[str, dict]:
    """Returns the full blueprint library as-is. The model picks/adapts
    from it — this function never chooses a blueprint for any question.
    """
    return BLUEPRINTS


def get_persona() -> dict:
    return PERSONA


def get_blueprint_competency_hints(blueprint_key: str) -> set[str]:
    """Competency tags to prefer when ranking evidence for this
    blueprint. Empty set (not an error) when the blueprint has no
    strong competency lean — retrieval falls back to JD-overlap/
    confidence/recency alone in that case.
    """
    return set(BLUEPRINT_COMPETENCY_HINTS.get(blueprint_key, []))