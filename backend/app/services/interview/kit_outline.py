"""Which questions an interview kit asks, decided from the job alone.

Each slot has a category, a topic and a standard wording, so the outline is a
complete kit by itself: it is what the user gets when the model can't be used.
Nothing about the candidate is read here, so no question can claim anything
about them.

Topics come from, in order of preference:

  technical depth  the job's skills: required, then implied (unless the guess
                   is a weak one), then nice to have
  system design    the architecture topics and design skills; senior and staff
                   jobs also get one on trade-offs
  behavioral       a fixed set of competencies for the seniority level
  role specific    focus areas not covered above, responsibilities,
                   capabilities and nice-to-have skills not yet asked about

Whatever the job's interview focus areas name explicitly comes first in its
category. A topic is asked about once, and every category has a question even
when the job gives nothing to build one from.
"""
import re

from app.schemas.interview.kit import KitQuestion, QuestionCategory
from app.schemas.job_intelligence.job_intelligence import EnrichedSkill, JobIntelligenceProfile
from app.services.evidence.matching import mentions_any
from app.services.job_intelligence.cleanup import plain_text

# How many questions of each category, by the job's seniority.
QUESTION_MIX: dict[str, dict[QuestionCategory, int]] = {
    "intern": {"technical_depth": 7, "system_design": 1, "behavioral": 4, "role_specific": 3},
    "junior": {"technical_depth": 7, "system_design": 2, "behavioral": 4, "role_specific": 3},
    "mid": {"technical_depth": 7, "system_design": 3, "behavioral": 4, "role_specific": 4},
    "senior": {"technical_depth": 7, "system_design": 4, "behavioral": 5, "role_specific": 4},
    "staff": {"technical_depth": 7, "system_design": 5, "behavioral": 5, "role_specific": 4},
}
_UNSTATED_SENIORITY = "mid"

_BEHAVIORAL: dict[str, tuple[str, str]] = {
    "teamwork": (
        "Working with others",
        "Tell me about a time you worked with others to deliver something. What was your part?",
    ),
    "problem_solving": (
        "Solving a hard problem",
        "Describe a difficult technical problem you worked through. How did you find the cause?",
    ),
    "failure_recovery": (
        "When things go wrong",
        "Tell me about something that didn't go to plan. What did you do, and what changed afterwards?",
    ),
    "ownership": (
        "Ownership",
        "Tell me about something you saw through from start to finish. Which decisions were yours?",
    ),
    "conflict_resolution": (
        "Disagreement",
        "Tell me about a technical disagreement you were part of. How was it settled?",
    ),
    "leadership": (
        "Leading",
        "Tell me about a time you led a piece of work. What did you do to keep it on track?",
    ),
    "mentorship": (
        "Helping others grow",
        "Tell me about a time you helped someone else get better at their work. What did you do?",
    ),
}
_EARLY_CAREER = ["teamwork", "problem_solving", "failure_recovery", "ownership"]
_BEHAVIORAL_BY_LEVEL: dict[str, list[str]] = {
    "intern": _EARLY_CAREER,
    "junior": _EARLY_CAREER,
    "mid": ["ownership", "problem_solving", "teamwork", "conflict_resolution"],
    "senior": ["leadership", "ownership", "conflict_resolution", "mentorship", "failure_recovery"],
    "staff": ["leadership", "conflict_resolution", "mentorship", "ownership", "failure_recovery"],
}

# Cycled, so a kit without a model doesn't repeat one sentence.
_TECHNICAL = [
    "Explain how you would use {topic} in practice. Which decisions matter, and what can go wrong?",
    "A teammate is new to {topic}. What would you make sure they understand first, and why?",
    "Something involving {topic} is misbehaving. How would you find out why?",
]
_DESIGN = "Walk through a design where this matters: {topic}. What would you build, and which trade-offs would you weigh?"
_TRADE_OFFS = "System design and trade-offs"
_A_DECISION = "A technical decision"
# Topics of the outline's own that name nothing a piece of work could mention.
GENERIC_TOPICS = frozenset({_TRADE_OFFS, _A_DECISION})
_TRADE_OFFS_TEXT = (
    "Design a service this role might own. Walk through its parts and its data, what fails first as use grows, "
    "and what you would trade to fix it."
)
_CROSS_TEAM = "Cross-team technical leadership"
_CROSS_TEAM_TEXT = (
    "Tell me about a technical change that needed more than one team. How did you get agreement and keep it moving?"
)

# Focus areas that Job Intelligence adds for seniority (interview_focus.py).
_TRADE_OFFS_FOCUS = "System design & trade-off reasoning"
_CROSS_TEAM_FOCUS = "Cross-team technical leadership"

_DESIGN_SKILL = re.compile(r"system design|distributed system|architecture|scalab", re.IGNORECASE)
_STRENGTH = {"good_knowledge": 0, "hands_on": 0, "not_specified": 1, "exposure": 2, "familiarity": 2}
_MAX_TOPIC = 120
_MAX_QUOTED = 220


def _key(text: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", "", text.lower())


def _shorten(text: str, limit: int) -> str:
    text = " ".join(text.split()).rstrip(" .;:,")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(" .;:,") + "…"


def spellings(skill: EnrichedSkill, aliases: dict[str, set[str]]) -> set[str]:
    """Every way a text might name this skill."""
    names = {skill.raw, skill.canonical, skill.canonical.replace("_", " "), *aliases.get(skill.canonical, ())}
    return {name.strip() for name in names if name.strip()}


def names_topic(text: str, names: set[str]) -> bool:
    """True when `text` uses one of the names, allowing for a singular or plural
    and for how it is hyphenated.
    """
    def loose(value: str) -> str:
        return " ".join(plain_text(value).replace("-", " ").split())

    forms = {loose(name) for name in names}
    forms |= {f"{form}s" for form in forms}
    forms |= {form[:-1] for form in forms if len(form) > 3 and form.endswith("s")}
    return mentions_any(loose(text), forms)


def _job_skills(job: JobIntelligenceProfile) -> list[EnrichedSkill]:
    """The job's skills, the ones most worth asking about first."""
    implied = [s for s in job.enriched_implicit_skills if s.confidence != "low"]
    ordered: list[EnrichedSkill] = []
    seen: set[str] = set()
    for band in (job.enriched_required_skills, implied, job.enriched_nice_to_have):
        for skill in sorted(band, key=lambda s: _STRENGTH.get(s.proficiency_signal, 1)):
            if skill.raw.strip() and skill.canonical not in seen:
                seen.add(skill.canonical)
                ordered.append(skill)
    return ordered


class _Outline:
    def __init__(self, job: JobIntelligenceProfile, aliases: dict[str, set[str]]):
        self.level = job.seniority_signal.level if job.seniority_signal.level in QUESTION_MIX else _UNSTATED_SENIORITY
        self.mix = QUESTION_MIX[self.level]
        self.aliases = aliases
        self.skills = _job_skills(job)
        self.questions: list[KitQuestion] = []
        self.asked: set[str] = set()  # topic keys and canonical skill names

    def count(self, category: QuestionCategory) -> int:
        return sum(q.category == category for q in self.questions)

    def mentioned(self, text: str) -> list[str]:
        return [s.canonical for s in self.skills if mentions_any(text, spellings(s, self.aliases))]

    def add(
        self, category: QuestionCategory, topic: str, text: str,
        skills: list[str] | None = None, competencies: list[str] | None = None,
    ) -> None:
        """Adds a question unless its category is full or the topic was asked.
        `skills` are those the question is about; when not given, it is tagged
        with the ones the topic mentions, which can still be asked about.
        """
        key = _key(topic)
        if not key or key in self.asked or self.count(category) >= self.mix[category]:
            return
        self.asked.update([key, *(_key(s) for s in skills or [])])
        self.questions.append(KitQuestion(
            category=category, topic=_shorten(topic, _MAX_TOPIC), text=text,
            skills=self.mentioned(topic) if skills is None else skills, competencies=competencies or [],
        ))

    def technical(self, skill: EnrichedSkill) -> None:
        if _key(skill.canonical) in self.asked:
            return
        topic = _shorten(skill.raw, _MAX_TOPIC)
        template = _TECHNICAL[self.count("technical_depth") % len(_TECHNICAL)]
        self.add("technical_depth", topic, template.format(topic=topic), [skill.canonical], ["technical_depth"])

    def design(self, topic: str, skills: list[str] | None = None) -> None:
        text = _DESIGN.format(topic=_shorten(topic, _MAX_TOPIC))
        self.add("system_design", topic, text, skills, ["technical_depth", "problem_solving"])


def _is_design_skill(skill: EnrichedSkill) -> bool:
    return skill.category == "Architecture & Design" or bool(_DESIGN_SKILL.search(skill.raw))


def build_outline(job: JobIntelligenceProfile, aliases: dict[str, set[str]] | None = None) -> list[KitQuestion]:
    """The kit's questions in their standard wording, grouped by category.
    `aliases` (canonical skill -> other spellings) helps spot a skill named
    inside a longer topic.
    """
    outline = _Outline(job, aliases or {})
    explicit = {_key(area) for area in job.interview_focus.explicit}

    def preferred(skill: EnrichedSkill) -> bool:
        return bool(explicit & {_key(skill.raw), _key(skill.canonical)})

    skills = sorted(outline.skills, key=lambda s: not preferred(s))  # stable: otherwise as ordered

    if outline.level in ("senior", "staff") or _TRADE_OFFS_FOCUS in job.interview_focus_areas:
        outline.add("system_design", _TRADE_OFFS, _TRADE_OFFS_TEXT, [], ["technical_depth", "problem_solving"])
    for topic in sorted(job.architecture_topics, key=lambda t: _key(t) not in explicit):
        outline.design(topic)
    for skill in skills:
        if _is_design_skill(skill):
            outline.design(_shorten(skill.raw, _MAX_TOPIC), [skill.canonical])
    if not outline.count("system_design"):
        outline.add("system_design", _TRADE_OFFS, _TRADE_OFFS_TEXT, [], ["technical_depth", "problem_solving"])

    for skill in skills:
        if not _is_design_skill(skill):
            outline.technical(skill)
    if not outline.count("technical_depth"):
        outline.add(
            "technical_depth", _A_DECISION,
            "Walk me through a technical decision you made. What were the options, and why did you choose yours?",
            [], ["technical_depth"],
        )

    if _CROSS_TEAM_FOCUS in job.interview_focus_areas or outline.level == "staff":
        outline.add("behavioral", _CROSS_TEAM, _CROSS_TEAM_TEXT, [], ["leadership"])
    for competency in _BEHAVIORAL_BY_LEVEL[outline.level]:
        # The cross-team question already asks about leading.
        if competency == "leadership" and _key(_CROSS_TEAM) in outline.asked:
            continue
        topic, text = _BEHAVIORAL[competency]
        outline.add("behavioral", topic, text, [], [competency])

    seniority_areas = {_key(_TRADE_OFFS_FOCUS), _key(_CROSS_TEAM_FOCUS)}
    skill_areas = {_key(name) for s in job.enriched_required_skills for name in (s.raw, s.canonical)}
    other_areas = [
        area for area in [*job.interview_focus.explicit, *job.interview_focus_areas]
        if _key(area) not in seniority_areas | skill_areas | {_key(t) for t in job.architecture_topics}
    ]
    for area in other_areas:
        outline.add(
            "role_specific", area, f"The interview may cover this: {_shorten(area, _MAX_QUOTED)}. "
            "What do you know about it, and how have you prepared?", competencies=["problem_solving"],
        )
    # Responsibilities leave room for one capability or nice-to-have question.
    nice = [s for s in skills if _key(s.canonical) not in outline.asked]
    reserved = 1 if job.capabilities or nice else 0
    for responsibility in job.responsibilities:
        if outline.count("role_specific") >= outline.mix["role_specific"] - reserved:
            break
        outline.add(
            "role_specific", responsibility,
            f"This role includes: “{_shorten(responsibility, _MAX_QUOTED)}”. How would you go about it?",
            competencies=["problem_solving"],
        )
    for skill in nice:
        if skill.requirement_type == "nice_to_have":
            outline.add(
                "role_specific", skill.raw,
                f"The job mentions {_shorten(skill.raw, _MAX_TOPIC)} as a plus. How familiar are you with it, "
                "and how would you get up to speed?", [skill.canonical], ["problem_solving"],
            )
    for capability in job.capabilities:
        if any(_key(capability) in asked for asked in outline.asked):  # said by a responsibility already
            continue
        outline.add(
            "role_specific", capability,
            f"This role asks for: “{_shorten(capability, _MAX_QUOTED)}”. How would you show you can do it?",
            competencies=["problem_solving"],
        )
    for responsibility in job.responsibilities:  # any room still left
        outline.add(
            "role_specific", responsibility,
            f"This role includes: “{_shorten(responsibility, _MAX_QUOTED)}”. How would you go about it?",
            competencies=["problem_solving"],
        )
    if not outline.count("role_specific"):
        role = _shorten(job.role, _MAX_TOPIC) if job.role else "this"
        outline.add(
            "role_specific", "Interest in the role",
            f"Why does {'this' if role == 'this' else 'the ' + role} role interest you, "
            "and what would you want to learn in it?", [], ["problem_solving"],
        )

    order = list(outline.mix)  # technical depth, system design, behavioral, role specific
    return sorted(outline.questions, key=lambda q: order.index(q.category))
