"""A reply that stops early must never be saved as if it were the whole job.
Only the LLM call is stubbed.
"""
import asyncio
import json

import httpx
import pytest
from openai import AuthenticationError, BadRequestError

from app.services.job_intelligence import extraction

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


def _reply(content: str):
    message = type("Message", (), {"content": content})()
    return type("Reply", (), {"choices": [type("Choice", (), {"message": message})()]})()


def _api_error(kind, status: int, code: str):
    response = httpx.Response(status, request=httpx.Request("POST", "http://llm.test"))
    return kind("failed", response=response, body={"code": code})


@pytest.fixture
def llm(monkeypatch):
    """Feed the extraction a queue of replies or errors; records each call."""
    queue, calls = [], []

    async def complete(**kwargs):
        calls.append(kwargs)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return _reply(item if isinstance(item, str) else json.dumps(item))

    monkeypatch.setattr(extraction, "chat_completion", complete)
    return queue, calls


def extract():
    return asyncio.run(extraction.extract_job_and_company("A job"))


@pytest.mark.parametrize("first", [
    CUT_OFF,
    '{"job": {"required_skills": [',
    _api_error(BadRequestError, 400, "json_validate_failed"),
], ids=["sections missing", "broken JSON", "provider rejected the JSON"])
def test_an_unusable_reply_is_asked_for_again(llm, first):
    queue, calls = llm
    queue.extend([first, COMPLETE])

    result = extract()

    assert [s.skill for s in result.job.nice_to_have] == ["Rust"]
    assert len(calls) == 2


def test_two_cut_off_replies_fail_instead_of_losing_requirements(llm):
    queue, calls = llm
    queue.extend([CUT_OFF, CUT_OFF])

    with pytest.raises(extraction.JobIntelligenceExtractionError):
        extract()
    assert len(calls) == 2


@pytest.mark.parametrize("error", [
    _api_error(AuthenticationError, 401, "invalid_api_key"),
    _api_error(BadRequestError, 400, "context_length_exceeded"),
], ids=["bad key", "posting too long"])
def test_errors_a_retry_cannot_fix_fail_at_once(llm, error):
    queue, calls = llm
    queue.extend([error, COMPLETE])

    with pytest.raises(extraction.JobIntelligenceExtractionError):
        extract()
    assert len(calls) == 1


@pytest.mark.parametrize("model,effort", [("openai/gpt-oss-120b", "low"), ("gemma3:4b", None)])
def test_reasoning_effort_is_lowered_only_for_models_that_take_it(llm, monkeypatch, model, effort):
    queue, calls = llm
    queue.append(COMPLETE)
    monkeypatch.setattr(extraction, "MODEL", model)

    extract()

    assert calls[0].get("reasoning_effort") == effort
