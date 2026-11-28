"""The study plan for one job, worked out from the user's record, their interview
kit and their practice. No model calls, and nothing is saved: it is true of the
record as it is when asked.

A gap is one of the job's skills the record shows too little of, by the same
matching as the skill-gap analysis. The most pressing come first: by severity,
then how the job asks for the skill, then the order the skills are usually
learnt in.

A gap is linked to LeetCode topics only where practising there bears on it: data
structures and algorithms (the topics of each, least practised first), a skill
that is itself a topic, and a few with their own LeetCode tag.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.interview.study import LeetcodeTopic, StudyGap, StudyPlan, StudyQuestion
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.services.interview.kit_evidence import evidence_is_stale, practice_counts
from app.services.interview.kit_outline import spellings
from app.services.interview.kit_store import get_kit
from app.services.interview.practice import kit_progress
from app.services.job_intelligence.builder import get_job_intelligence
from app.services.leetcode.leetcode_taxonomy import CANONICAL_TOPICS, PRACTICE_TAGS, tag_slug, topic_totals
from app.services.skill_gap.comparison import load_evidence_view, match_requirements
from app.services.taxonomy.skill_taxonomy import get_curriculum_rank

# An answer covering fewer than this share of its headings is worth another go.
WEAK_SCORE = 0.5
_MAX_TOPICS = 5
_SEVERITY_ORDER = {"critical": 0, "moderate": 1, "minor": 2}
_REQUIREMENT_ORDER = {"required": 0, "implicit": 1, "nice_to_have": 2}
# Skills with a LeetCode tag outside the interview topics: slug -> (name, tag).
_OTHER_TAGS = {"sql": ("Database", "database"), "concurrency": ("Concurrency", "concurrency")}

_HIDDEN = (
    "You hid this skill from your record.",
    "If you have used it, restore it in your profile. If not, learn the basics.",
)
_NOTHING = (
    "Nothing in your record shows it.",
    "Learn it well enough to explain it. Once you have used it in real work, add that to your profile.",
)
_TOO_LITTLE = (
    "Your record shows too little of it to count.",
    "Build or write up work that uses it, so you have an example to talk about.",
)
_THIN = (
    "Your record shows it only thinly.",
    "Build or write up work that uses it, so you have an example to talk about.",
)
_PRACTISE = "Solve problems in these topics, least practised first, then sync LeetCode."

_NO_KIT = "Generate an interview kit for this job to see which questions these gaps affect."
_STALE_KIT = (
    "Your record has changed since the kit's evidence was matched, so which questions lack an example may be "
    "out of date."
)
_NO_PRACTICE_COUNTS = "Sync LeetCode to see how much you have already solved in each topic."


def _link(topic: str, tag: str, solved: int | None) -> LeetcodeTopic:
    return LeetcodeTopic(topic=topic, url=f"https://leetcode.com/tag/{tag}/", solved=solved)


def leetcode_topics(skill: str, names: set[str], counts: dict[str, int]) -> list[LeetcodeTopic]:
    """The LeetCode topics that bear on a skill known by any of `names`.
    `counts` is tag -> problems solved, empty when nothing has been synced.
    """
    totals = topic_totals(counts)

    def solved(count: int) -> int | None:
        return count if counts else None

    if skill in PRACTICE_TAGS:
        found = [
            _link(topic, next(tag for tag in tags if tag in PRACTICE_TAGS[skill]), solved(totals[topic]))
            for topic, tags in CANONICAL_TOPICS.items() if PRACTICE_TAGS[skill] & set(tags)
        ]
        found.sort(key=lambda link: link.solved or 0)  # stable: otherwise in the usual order
        return found[:_MAX_TOPICS]

    slugs = {tag_slug(name) for name in names}
    found = []
    for topic, tags in CANONICAL_TOPICS.items():
        tag = next((t for t in tags if t in slugs), tags[0] if tag_slug(topic) in slugs else None)
        if tag is not None:
            found.append(_link(topic, tag, solved(totals[topic])))
    found += [_link(topic, tag, solved(counts.get(tag, 0))) for slug, (topic, tag) in _OTHER_TAGS.items()
              if slug in slugs]
    return found[:_MAX_TOPICS]


def _gaps(job: JobIntelligenceProfile, missing: list, partial: list, hidden: set[str], counts: dict) -> list[StudyGap]:
    wanted = job.canonical_skills_map
    job_skills: dict[str, list] = {}
    for skill in [*job.enriched_required_skills, *job.enriched_implicit_skills, *job.enriched_nice_to_have]:
        job_skills.setdefault(skill.canonical, []).append(skill)

    gaps = []
    for status, entry in [*(("missing", m) for m in missing), *(("partial", p) for p in partial)]:
        mine = job_skills.get(entry.skill, [])
        names = {name for skill in mine for name in spellings(skill, {})} or {entry.skill}
        topics = leetcode_topics(entry.skill, names, counts)
        if entry.skill in hidden:
            why, action = _HIDDEN
        elif status == "partial":
            why, action = _THIN
        else:
            why, action = _TOO_LITTLE if entry.supporting else _NOTHING
        if entry.skill in PRACTICE_TAGS and entry.skill not in hidden:
            action = _PRACTISE
        gaps.append(StudyGap(
            skill=entry.skill, name=mine[0].raw if mine else entry.skill.replace("_", " "), status=status,
            severity=entry.severity, requirement=wanted[entry.skill], why=why, action=action, leetcode=topics,
        ))
    gaps.sort(key=lambda g: (
        _SEVERITY_ORDER[g.severity], _REQUIREMENT_ORDER.get(g.requirement, 2), get_curriculum_rank(g.skill), g.name,
    ))
    return gaps


async def build_study_plan(db: AsyncSession, user_id, job_intelligence_id) -> StudyPlan | None:
    """What to study for this job. None when the user has no such job."""
    job = await get_job_intelligence(db, user_id, job_intelligence_id)
    if job is None:
        return None
    wanted = job.canonical_skills_map
    counts = await practice_counts(db, user_id)
    gaps: list[StudyGap] = []
    if wanted:
        view = await load_evidence_view(db, user_id, set(wanted))
        _have, partial, missing = match_requirements(wanted, view)
        gaps = _gaps(job, missing, partial, view.hidden, counts)
    plan = StudyPlan(
        job_intelligence_id=job_intelligence_id, role=job.role, company=job.company, gaps=gaps,
    )

    saved = await get_kit(db, user_id, job_intelligence_id)
    if saved is None:
        plan.notes.append(_NO_KIT)
    else:
        progress = await kit_progress(db, user_id, job_intelligence_id, saved.kit.version)
        asked = {
            q.question_id: StudyQuestion(question_id=q.question_id, text=q.text, latest_score=q.latest_score)
            for q in progress.questions
        }
        for gap in gaps:
            gap.questions = [asked[q.id] for q in saved.questions if gap.skill in q.skills]
        lacking = {gap.skill for gap in gaps}
        plan.unanswered = [
            asked[q.id] for q in saved.questions if q.thin_evidence and not lacking & set(q.skills)
        ]
        plan.weak = [q for q in asked.values() if q.latest_score is not None and q.latest_score < WEAK_SCORE]
        plan.weakest_category = progress.weakest
        plan.kit_version = saved.kit.version
        if await evidence_is_stale(db, user_id, saved.kit):
            plan.notes.append(_STALE_KIT)
    if not counts and any(gap.leetcode for gap in gaps):
        plan.notes.append(_NO_PRACTICE_COUNTS)
    return plan
