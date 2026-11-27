"""A job's skills come out under the same names a user's evidence is stored
under. Runs the real build pipeline on the real database; only the LLM calls
are stubbed.
"""
import pytest

from app.schemas.job_intelligence.job_intelligence import ExtractedJobAndCompany
from app.services.job_intelligence.builder import build_job_intelligence
from app.services.resume.skill_classifier import resolve_skills
from tests.api.test_evidence import run

POSTING = (
    "Backend Engineering Intern\n"
    "You will maintain CI/CD pipelines.\n"
    "Must have: C/C++, GoLang, data structures and algorithms, analytical thinking, AWS (S3, EKS).\n"
    "Good to have: Apache Kafka, Python.\n"
)


@pytest.fixture
def stubbed_llm(monkeypatch):
    def entry(skill):
        return {"skill": skill}

    async def extract(raw_text):
        return ExtractedJobAndCompany.model_validate({"job": {
            "role": "Backend Engineering Intern",
            "required_skills": [entry(s) for s in (
                "C/C++", "GoLang", "Data structures and algorithms", "Analytical thinking", "AWS (S3, EKS)",
            )],
            "nice_to_have": [entry("Apache Kafka"), entry("Python"), entry("Golang")],
            "implicit_skills": [
                {"skill": "Git", "evidence": "maintain CI/CD pipelines"},
                {"skill": "Jira", "evidence": "tracks work in sprints"},
                {"skill": "S3", "evidence": "AWS (S3, EKS)"},
            ],
        }})

    async def classify(raw_strings):
        return {raw: (None, False) for raw in raw_strings}

    monkeypatch.setattr("app.services.job_intelligence.builder.extract_job_and_company", extract)
    monkeypatch.setattr("app.services.resume.skill_classifier._classify_via_llm", classify)


def test_extracted_skills_are_split_named_consistently_and_not_repeated(seeded, stubbed_llm):
    async def build(db):
        profile, _ = await build_job_intelligence(db, seeded["bob_id"], POSTING)
        resume_side = await resolve_skills({"Go", "C++", "Amazon S3", "Kafka"}, db)
        await db.rollback()
        return profile, resume_side

    profile, resume_side = run(build)

    required = [s.canonical for s in profile.enriched_required_skills]
    assert required == ["c", "cpp", "go", "data_structures", "algorithms", "aws", "s3", "eks"]
    assert [s.canonical for s in profile.enriched_nice_to_have] == ["kafka", "python"]
    # Jira's quote isn't in the posting; S3 is already required.
    assert [s.canonical for s in profile.enriched_implicit_skills] == ["git"]
    # The same technologies written the way a resume would write them.
    assert set(resume_side.values()) <= set(required) | {"kafka"}
    assert "analytical" not in " ".join(profile.resume_keywords)
