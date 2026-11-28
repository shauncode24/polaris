"""A job reply that stops early must never be saved as if it were the whole
job. Only the model is stubbed.
"""
import asyncio

import pytest
from openai import AuthenticationError

from app.services.job_intelligence import extraction
from tests.llm_stub import api_error, model  # noqa: F401 (model is a fixture)

COMPLETE = {
    "job": {
        "required_skills": [{"skill": "Python"}],
        "implicit_skills": [],
        "nice_to_have": [{"skill": "Rust"}],
        "qualification_requirements": {},
    },
    "company": {},
}
# Valid JSON, but everything after the required skills is missing.
CUT_OFF = {"job": {"required_skills": [{"skill": "Python"}]}}


def extract():
    return asyncio.run(extraction.extract_job_and_company("A job"))


def test_a_cut_off_reply_is_asked_for_again(model):
    model.will(CUT_OFF, COMPLETE)

    result = extract()

    assert [s.skill for s in result.job.nice_to_have] == ["Rust"]
    assert len(model.requests) == 2


@pytest.mark.parametrize("missing", ["required_skills", "implicit_skills", "nice_to_have",
                                     "qualification_requirements"])
def test_every_job_section_is_needed(model, missing):
    partial = {"job": {k: v for k, v in COMPLETE["job"].items() if k != missing}, "company": {}}
    model.will(partial, partial)

    with pytest.raises(extraction.JobIntelligenceExtractionError):
        extract()


def test_a_reply_without_the_company_is_incomplete(model):
    partial = {"job": COMPLETE["job"]}
    model.will(partial, partial)

    with pytest.raises(extraction.JobIntelligenceExtractionError):
        extract()


def test_the_failure_message_can_be_shown_to_the_user(model):
    model.will(api_error(AuthenticationError, 401))

    with pytest.raises(extraction.JobIntelligenceExtractionError, match="rejected its API key"):
        extract()
