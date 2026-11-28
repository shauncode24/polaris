"""The shared model call: retries, cut-off replies, errors and logging."""
import asyncio
import json
import logging
import re
from pathlib import Path

import httpx
import pytest
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    InternalServerError,
    RateLimitError,
)
from pydantic import BaseModel

from app.core import llm
from app.core.llm import (
    LLMError,
    LLMNotConfiguredError,
    LLMReplyError,
    LLMUnavailableError,
    Prompt,
    llm_json,
)
from tests.llm_stub import api_error, model, reply  # noqa: F401 (model is a fixture)


class Answer(BaseModel):
    title: str = ""
    items: list[str] = []


GOOD = {"title": "t", "items": ["a"]}
_REQUEST = httpx.Request("POST", "http://llm.invalid")


def ask(fallback=None, **options):
    return asyncio.run(llm_json(Prompt("sys", {"q": 1}), Answer, fallback, label="test", **options))


# --- the request ------------------------------------------------------------

def test_a_good_reply_is_returned_as_the_schema(model):
    model.will(GOOD)

    result = ask()

    assert result.value == Answer(**GOOD)
    assert result.degraded is False
    request = model.requests[0]
    assert request["messages"] == [
        {"role": "system", "content": "sys"}, {"role": "user", "content": json.dumps({"q": 1})},
    ]
    assert request["response_format"] == {"type": "json_object"}
    assert request["model"] == llm.MODEL
    assert "timeout" not in request and "max_tokens" not in request


def test_text_is_sent_as_it_is(model):
    model.will(GOOD)

    asyncio.run(llm_json(Prompt("sys", "plain text"), Answer, label="test"))

    assert model.requests[0]["messages"][1]["content"] == "plain text"


def test_reasoning_models_get_low_effort_and_room_to_reason(model):
    model.will(GOOD)

    ask(model="openai/gpt-oss-20b", max_tokens=300, timeout=5)

    request = model.requests[0]
    assert request["reasoning_effort"] == "low"
    assert request["max_tokens"] > 300
    assert request["timeout"] == 5


def test_other_models_get_exactly_what_was_asked_for(model):
    model.will(GOOD)

    ask(model="qwen/qwen3", max_tokens=300)

    assert "reasoning_effort" not in model.requests[0]
    assert model.requests[0]["max_tokens"] == 300


# --- unusable replies -------------------------------------------------------

def _reject_empty(payload):
    if not payload["items"]:
        raise ValueError("no items")
    return payload


@pytest.mark.parametrize("bad,options", [
    ('{"title": "t", "items": [', {}),
    (["not", "an", "object"], {}),
    ({"title": "t", "items": "not a list"}, {}),
    ({"title": "t"}, {"expect": ("title", "items")}),
    (reply(GOOD, finish_reason="length"), {}),
    ({"title": "t", "items": []}, {"prepare": _reject_empty}),
    (api_error(BadRequestError, 400, "json_validate_failed"), {}),
], ids=["broken JSON", "not an object", "wrong shape", "section missing", "hit the token limit",
        "rejected by the caller", "provider rejected the JSON"])
def test_an_unusable_reply_is_asked_for_once_more(model, bad, options):
    model.will(bad, GOOD)

    assert ask(**options).value == Answer(**GOOD)
    assert len(model.requests) == 2
    assert model.requests[1]["messages"] == model.requests[0]["messages"]


def test_a_cut_off_reply_is_never_returned_as_complete(model):
    model.will({"title": "t"}, {"title": "t"})

    with pytest.raises(LLMReplyError):
        ask(expect=("items",))
    assert len(model.requests) == 2


def test_two_unusable_replies_give_the_fallback(model):
    model.will("nonsense", "nonsense")

    result = ask(lambda: Answer(title="fallback"))

    assert (result.value.title, result.degraded) == ("fallback", True)


def test_a_repair_shows_the_model_what_was_wrong(model):
    model.will({"title": "t"}, GOOD)

    ask(expect=("items",), repair=True, temperature=0.7)

    first, second = model.requests
    assert second["messages"][:2] == first["messages"]
    assert json.loads(second["messages"][2]["content"]) == {"title": "t"}
    assert "no items" in second["messages"][3]["content"]
    assert (first["temperature"], second["temperature"]) == (0.7, 0)


# --- failures a second attempt can't fix ------------------------------------

@pytest.mark.parametrize("error,says", [
    (api_error(RateLimitError, 429), "usage limit"),
    (api_error(AuthenticationError, 401), "GROQ_API_KEY"),
    (api_error(BadRequestError, 400, "context_length_exceeded"), "too long"),
    (api_error(BadRequestError, 400, "model_not_found"), "couldn't process"),
    (api_error(InternalServerError, 500), "unavailable"),
    (APITimeoutError(request=_REQUEST), "too long to answer"),
    (APIConnectionError(request=_REQUEST), "unavailable"),
    (RuntimeError("provider detail that users must not see"), "request failed"),
], ids=["rate limit", "bad key", "too long", "unknown model", "server error", "timeout", "no connection",
        "anything else"])
def test_a_failed_request_fails_at_once_with_a_readable_message(model, error, says):
    model.will(error, GOOD)

    with pytest.raises(LLMUnavailableError) as raised:
        ask()

    assert says in str(raised.value)
    assert "provider detail" not in str(raised.value)
    assert raised.value.__cause__ is error
    assert len(model.requests) == 1


def test_a_failed_request_gives_the_fallback(model):
    model.will(api_error(RateLimitError, 429))

    assert ask(lambda: Answer(title="fallback")).degraded is True


def test_a_missing_key_is_reported_without_calling_anything(model, monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "")

    with pytest.raises(LLMNotConfiguredError, match="GROQ_API_KEY is missing"):
        ask()
    assert ask(lambda: Answer()).degraded is True
    assert model.requests == []


# --- logging ----------------------------------------------------------------

def test_each_attempt_logs_its_tokens_and_time(model, caplog, monkeypatch):
    # The migration run in the database tests switches existing loggers off.
    monkeypatch.setattr(logging.getLogger("app.core.llm"), "disabled", False)
    answered = reply(GOOD)
    details = type("Details", (), {"reasoning_tokens": 7})()
    answered.usage = type("Usage", (), {
        "prompt_tokens": 100, "completion_tokens": 20, "completion_tokens_details": details,
    })()
    model.will(answered)

    with caplog.at_level(logging.INFO, logger="app.core.llm"):
        ask()

    line = next(r.getMessage() for r in caplog.records if "latency_ms" in r.getMessage())
    for part in ("label=test", "attempt=1", "prompt_tokens=100", "completion_tokens=20",
                 "reasoning_tokens=7", "finish=stop"):
        assert part in line
    assert "sys" not in line.split("label=")[1]  # no prompt text at this level


# --- the real client, with a fake network -----------------------------------

def _completion(content: str):
    return httpx.Response(200, json={
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
    })


def _status(code: int):
    # "retry-after-ms" keeps the library's backoff short in tests.
    return httpx.Response(code, json={"error": {"message": "x"}}, headers={"retry-after-ms": "1"})


@pytest.fixture
def network(monkeypatch):
    """Runs the real client against queued HTTP responses."""
    responses, seen = [], []

    def handle(request):
        seen.append(request)
        return responses.pop(0)

    client = llm.build_client(
        max_retries=2, http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
    )
    monkeypatch.setattr(llm, "client", client)
    return responses, seen


@pytest.mark.parametrize("code", [429, 500, 503])
def test_rate_limits_and_server_errors_are_retried(network, code):
    responses, seen = network
    responses.extend([_status(code), _status(code), _completion(json.dumps(GOOD))])

    assert ask().value == Answer(**GOOD)
    assert len(seen) == 3


def test_retries_are_bounded(network):
    responses, seen = network
    responses.extend([_status(500)] * 5)

    with pytest.raises(LLMUnavailableError):
        ask()
    assert len(seen) == 3


def test_a_refused_key_is_not_retried(network):
    responses, seen = network
    responses.extend([_status(401)] * 3)

    with pytest.raises(LLMUnavailableError):
        ask()
    assert len(seen) == 1


def test_json_wrapped_in_a_code_fence_is_read(network):
    responses, _ = network
    responses.append(_completion("```json\n" + json.dumps(GOOD) + "\n```"))

    assert ask().value == Answer(**GOOD)


def test_the_client_has_a_timeout():
    assert llm.build_client().timeout == llm.TIMEOUT_SECONDS > 0


# --- nothing goes around it -------------------------------------------------

def test_every_model_call_goes_through_the_shared_helper():
    app = Path(llm.__file__).parents[1]
    offenders = [
        str(path.relative_to(app))
        for path in app.rglob("*.py")
        if path.name != "llm.py" and path.parent.name != "scripts"
        and re.search(r"AsyncOpenAI|chat\.completions|chat_completion", path.read_text(encoding="utf8"))
    ]
    assert offenders == []


def test_no_feature_hard_codes_a_model_name():
    app = Path(llm.__file__).parents[1]
    offenders = [
        str(path.relative_to(app))
        for path in app.rglob("*.py")
        if path.name != "llm.py"
        and re.search(r"[\"'](llama|gpt|openai/|qwen|gemini)[\w./-]*[\"']", path.read_text(encoding="utf8"))
        and re.search(r"model\s*=\s*[\"']|MODEL.*[\"'](llama|openai/|qwen|gemini)", path.read_text(encoding="utf8"))
    ]
    assert offenders == []


def test_errors_share_one_base_with_a_status():
    assert [(e.status_code, issubclass(e, LLMError)) for e in
            (LLMNotConfiguredError, LLMUnavailableError, LLMReplyError)] == [(503, True), (503, True), (502, True)]
