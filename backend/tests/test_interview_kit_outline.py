"""Which questions an interview kit asks, decided from the job. No model, no database."""
from collections import Counter

import pytest

from app.schemas.interview.kit import CATEGORIES, MAX_QUESTION_LENGTH
from app.schemas.job_intelligence.job_intelligence import JobIntelligenceProfile
from app.services.interview.kit_outline import QUESTION_MIX, build_outline


def skill(raw, kind="required", **fields):
    return {"raw": raw, "canonical": raw.lower().replace(" ", "_"), "category": "General Technical",
            "curriculum_phase": "General Technical", "requirement_type": kind, **fields}


def job(level="mid", required=(), implicit=(), nice=(), **fields) -> JobIntelligenceProfile:
    def entries(items, kind):
        return [skill(item, kind) if isinstance(item, str) else item for item in items]

    return JobIntelligenceProfile.model_validate({
        "role": "Backend Engineer", "seniority_signal": {"level": level},
        "enriched_required_skills": entries(required, "required"),
        "enriched_implicit_skills": entries(implicit, "implicit"),
        "enriched_nice_to_have": entries(nice, "nice_to_have"),
        **fields,
    })


def topics(questions, category) -> list[str]:
    return [q.topic for q in questions if q.category == category]


MANY = [f"Skill{n}" for n in range(20)]
FULL = {
    "required": MANY,
    "architecture_topics": [f"Topic{n}" for n in range(10)],
    "responsibilities": [f"Run service number {n}." for n in range(10)],
}


@pytest.mark.parametrize("level", QUESTION_MIX)
def test_the_number_of_questions_in_each_category_follows_the_seniority(level):
    questions = build_outline(job(level, **FULL))

    assert Counter(q.category for q in questions) == QUESTION_MIX[level]


def test_an_unstated_seniority_is_treated_as_mid_level():
    questions = build_outline(job("unspecified", **FULL))

    assert Counter(q.category for q in questions) == QUESTION_MIX["mid"]


def test_questions_come_grouped_by_category():
    categories = [q.category for q in build_outline(job(**FULL))]

    assert categories == sorted(categories, key=CATEGORIES.index)


def test_technical_questions_take_required_skills_first_and_the_strongest_asked_for_first():
    questions = build_outline(job(
        required=[
            skill("Redis", proficiency_signal="familiarity"),
            skill("Kafka"),
            skill("Python", proficiency_signal="good_knowledge"),
        ],
        implicit=[skill("Linux", "implicit", confidence="high"), skill("Perl", "implicit", confidence="low")],
        nice=["Rust"],
    ))

    assert topics(questions, "technical_depth") == ["Python", "Kafka", "Redis", "Linux", "Rust"]
    assert not any("Perl" in q.text for q in questions)  # a weak guess is not asked about
    first = questions[0]
    assert (first.skills, first.competencies, first.origin) == (["python"], ["technical_depth"], "outline")
    assert "Python" in first.text


def test_what_the_interview_is_said_to_cover_comes_first():
    questions = build_outline(job(
        required=["Python", "Kafka"], architecture_topics=["Caching", "Scalability"],
        interview_focus={"explicit": ["Kafka", "Scalability"]},
    ))

    assert topics(questions, "technical_depth") == ["Kafka", "Python"]
    assert topics(questions, "system_design") == ["Scalability", "Caching"]


def test_a_design_skill_is_a_system_design_question():
    questions = build_outline(job(
        required=["System design", "Python", skill("Microservices", category="Architecture & Design")],
    ))

    assert topics(questions, "system_design") == ["System design", "Microservices"]
    assert topics(questions, "technical_depth") == ["Python"]
    assert [q.skills for q in questions if q.category == "system_design"] == [["system_design"], ["microservices"]]


def test_a_topic_is_asked_about_once():
    questions = build_outline(job(
        required=["Microservices design", "Caching"], nice=["Python"], architecture_topics=["Caching"],
        capabilities=["Python"], interview_focus_areas=["Caching", "Python"],
    ))

    asked = [q.topic.lower() for q in questions]
    assert len(asked) == len(set(asked))
    assert asked.count("caching") == 1


def test_a_skill_another_topic_only_mentions_still_gets_its_own_question():
    questions = build_outline(job(required=["Postgres"], architecture_topics=["Sharding Postgres"]))

    assert topics(questions, "technical_depth") == ["Postgres"]
    assert topics(questions, "system_design") == ["Sharding Postgres"]


@pytest.mark.parametrize("level", ["senior", "staff"])
def test_senior_jobs_are_asked_about_trade_offs_and_leading(level):
    questions = build_outline(job(level, architecture_topics=["Caching"]))

    assert topics(questions, "system_design") == ["System design and trade-offs", "Caching"]
    assert any("leadership" in q.competencies for q in questions if q.category == "behavioral")


def test_a_junior_job_is_not_asked_about_leading():
    questions = build_outline(job("junior"))

    behavioral = [c for q in questions if q.category == "behavioral" for c in q.competencies]
    assert behavioral == ["teamwork", "problem_solving", "failure_recovery", "ownership"]


def test_leading_across_teams_is_asked_once():
    questions = build_outline(job("staff", interview_focus_areas=["Cross-team technical leadership"]))

    leading = [q.topic for q in questions if "leadership" in q.competencies]
    assert leading == ["Cross-team technical leadership"]


def test_role_questions_come_from_focus_areas_responsibilities_and_extras():
    questions = build_outline(job(
        required=["Python"], nice=[skill(f"Extra{n}", "nice_to_have") for n in range(10)],
        responsibilities=["Own the billing service and its Python jobs."],
        interview_focus_areas=["Python", "Payment compliance"],
    ))

    role = [q for q in questions if q.category == "role_specific"]
    assert [q.topic for q in role][:2] == ["Payment compliance", "Own the billing service and its Python jobs"]
    assert role[1].skills == ["python"]  # named in the responsibility
    assert len(role) == QUESTION_MIX["mid"]["role_specific"]
    assert all(q.topic.startswith("Extra") for q in role[2:])


def test_one_role_question_is_kept_for_what_the_responsibilities_do_not_cover():
    questions = build_outline(job(**{"capabilities": ["Handle incidents"], "responsibilities": FULL["responsibilities"]}))

    role = topics(questions, "role_specific")
    assert len(role) == 4
    assert role[-1] == "Handle incidents"


def test_a_capability_a_responsibility_already_says_is_not_asked_again():
    questions = build_outline(job(
        responsibilities=["Build billing services, including their tests."],
        capabilities=["Build billing services", "Handle incidents"],
    ))

    assert topics(questions, "role_specific") == [
        "Build billing services, including their tests", "Handle incidents"]


def test_other_spellings_find_a_skill_inside_a_topic():
    profile = job(required=["PostgreSQL"], architecture_topics=["Sharding Postgres"])

    questions = build_outline(profile, {"postgresql": {"postgres"}})

    assert next(q for q in questions if q.topic == "Sharding Postgres").skills == ["postgresql"]


def test_a_job_with_nothing_extracted_still_has_every_category():
    questions = build_outline(JobIntelligenceProfile())

    assert {q.category for q in questions} == set(CATEGORIES)
    assert all(q.text and q.topic for q in questions)


def test_very_long_job_text_still_makes_questions_of_a_sensible_length():
    long = "design and operate " * 60
    questions = build_outline(job(
        role=long, required=["x" * 500], nice=["y" * 500], architecture_topics=[long], capabilities=["z " * 300],
        responsibilities=[long], interview_focus_areas=["w " * 300],
    ))

    assert all(len(q.text) <= MAX_QUESTION_LENGTH and len(q.topic) <= 120 for q in questions)
    assert any(q.topic.endswith("…") for q in questions)


def test_the_same_job_always_gets_the_same_outline():
    profile = job("senior", **FULL)

    assert build_outline(profile) == build_outline(profile)
