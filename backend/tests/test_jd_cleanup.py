"""The deterministic clean-up of extracted job skills. The examples are ones
real postings produced during step 22.
"""
import pytest

from app.schemas.job_intelligence.job_intelligence import (
    EnrichedSkill,
    ExtractedImplicitSkill,
    ExtractedSkillRequirement,
)
from app.services.job_intelligence.cleanup import (
    clean_implicit,
    clean_requirements,
    drop_repeats,
    is_soft_skill,
    split_skill,
)


@pytest.mark.parametrize("entry,expected", [
    ("C/C++", ["C", "C++"]),
    ("Ruby/Rails", ["Ruby", "Rails"]),
    ("Java/TypeScript/Python", ["Java", "TypeScript", "Python"]),
    ("React or Angular", ["React", "Angular"]),
    ("HTML, CSS, JavaScript", ["HTML", "CSS", "JavaScript"]),
    ("Data structures and algorithms", ["Data structures", "Algorithms"]),
    ("AWS (S3, EKS, and IAM)", ["AWS", "S3", "EKS", "IAM"]),
    ("APM tools (e.g. Prometheus, Grafana)", ["APM tools", "Prometheus", "Grafana"]),
    ("Linux (Ubuntu)", ["Linux"]),
    ("web accessibility (WCAG)", ["web accessibility"]),
    ("Kafka (preferred)", ["Kafka"]),
    ("Micro‑services", ["Micro-services"]),  # non-breaking hyphen
])
def test_entries_naming_several_skills_are_split(entry, expected):
    assert split_skill(entry) == expected


@pytest.mark.parametrize("entry", [
    "CI/CD", "CI/CD pipelines", "TCP/IP", "UI/UX", "A/B testing",
    "Ruby on Rails", "Node.js", "C#", "Research and development of large distributed storage systems",
])
def test_single_skills_are_left_whole(entry):
    assert split_skill(entry) == [entry]


@pytest.mark.parametrize("entry", [
    "communication", "Analytical thinking", "Logical thinking", "Systems Thinking",
    "Analytical and problem-solving skills", "Excellent verbal and written communication",
    "Strong problem solving", "Attention to detail", "Teamwork",
])
def test_personal_traits_are_recognised(entry):
    assert is_soft_skill(entry)


@pytest.mark.parametrize("entry", [
    "Communication protocols", "Distributed systems", "Systems design", "Data analytics", "Python",
])
def test_technical_skills_are_not_taken_for_traits(entry):
    assert not is_soft_skill(entry)


def test_split_entries_keep_their_proficiency_and_traits_are_removed():
    cleaned = clean_requirements([
        ExtractedSkillRequirement(skill="Java/Scala", proficiency_signal="hands_on"),
        ExtractedSkillRequirement(skill="Analytical thinking"),
    ])
    assert [(c.skill, c.proficiency_signal) for c in cleaned] == [("Java", "hands_on"), ("Scala", "hands_on")]


@pytest.mark.parametrize("entry,expected", [
    # A trait phrase is dropped whole, even though it would split into
    # fragments that no longer look like traits.
    ("Verbal or written communication", []),
    # A trait listed beside a technology goes; the technology stays.
    ("Python, communication", ["Python"]),
])
def test_traits_are_removed_before_and_after_splitting(entry, expected):
    cleaned = clean_requirements([ExtractedSkillRequirement(skill=entry)])
    assert [c.skill for c in cleaned] == expected


@pytest.mark.parametrize("entry", [
    "Design", "Deploy", "Maintain", "Open-source contribution", "Open source contributions",
    "GitHub projects", "weekend side projects", "Ad tech industry experience", "Product company experience",
])
def test_verbs_and_candidate_history_are_not_skills(entry):
    assert clean_requirements([ExtractedSkillRequirement(skill=entry)]) == []


@pytest.mark.parametrize("entry", [
    "Testing", "Debugging", "Design patterns", "System design", "User experience", "GitHub Actions",
    "Open source technologies",
])
def test_skills_that_resemble_them_are_kept(entry):
    assert [c.skill for c in clean_requirements([ExtractedSkillRequirement(skill=entry)])] == [entry]


POSTING = """What you'll do
- Design, build and maintain CI/CD pipelines for all environments.
- Participate in code reviews, providing constructive feedback.
- Aim for sub‑minute data latency.
"""


def _implicit(skill, evidence):
    return ExtractedImplicitSkill(skill=skill, evidence=evidence, confidence="high")


def test_inferred_skills_need_a_quote_that_is_in_the_posting():
    kept = clean_implicit([
        _implicit("Git", "maintain CI/CD pipelines"),
        _implicit("Stream processing", "sub-minute data latency."),  # differs only in typography
        _implicit("Pull requests", "Participate in code\n reviews"),  # differs only in spacing
        _implicit("Version control", "collaborate with designers, participate in code reviews"),
        _implicit("Jenkins", ""),
    ], POSTING)
    assert [k.skill for k in kept] == ["Git", "Stream processing", "Pull requests"]


def _enriched(canonical, requirement_type):
    return EnrichedSkill(raw=canonical, canonical=canonical, category="c", curriculum_phase="p",
                         requirement_type=requirement_type)


def test_each_skill_ends_up_in_one_band():
    required = [_enriched("sql", "required")]
    implicit = [_enriched("sql", "implicit"), _enriched("git", "implicit"), _enriched("gcp", "implicit")]
    nice = [_enriched("sql", "nice_to_have"), _enriched("gcp", "nice_to_have")]

    kept_implicit, kept_nice = drop_repeats(required, implicit, nice)

    assert [s.canonical for s in kept_implicit] == ["git"]
    assert [s.canonical for s in kept_nice] == ["gcp"]
