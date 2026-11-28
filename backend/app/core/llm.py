"""The one way the app talks to the language model (any OpenAI-compatible API,
currently Groq).

Features call `llm_json`. It owns everything that is the same for every call:

  * a timeout, and bounded retries with backoff on rate limits, server errors
    and dropped connections (done by the client library)
  * one more attempt when the reply can't be used: not JSON, the wrong shape,
    or cut off before the end
  * one log line per attempt with the tokens spent and the time taken
  * errors whose message can be shown to a user, including a missing API key
  * each user's daily number of calls (see llm_budget.py)
  * the caller's fallback, when it has one

The model can run out of room and still send valid JSON with the end missing.
Reply schemas default their fields to empty, so name the keys a finished reply
always has in `expect`; otherwise the missing part is silently lost.
"""
import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, NamedTuple, TypeVar

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from app.core import llm_budget
from app.core import settings as _settings  # noqa: F401  (loads .env before it is read below)

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
BASE_URL = os.environ.get("GROQ_BASE_URL") or "https://api.groq.com/openai/v1"
MODEL = os.environ.get("GROQ_MODEL") or "openai/gpt-oss-120b"
TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS") or 60)
MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES") or 2)

# Attempts at getting a usable reply, on top of the transport retries.
_REPLY_ATTEMPTS = 2
# Reasoning models spend part of a reply's token limit on reasoning, so a
# caller's limit, which is meant for the answer, gets this much on top.
_REASONING_ALLOWANCE = 1200


class LLMError(Exception):
    """A model call that produced nothing usable. The message is written to be
    shown to a user; the technical detail is logged and kept as the cause.
    """
    status_code = 502


class LLMNotConfiguredError(LLMError):
    status_code = 503


class LLMUnavailableError(LLMError):
    """The service couldn't be reached or refused the request. Asking again
    straight away won't help.
    """
    status_code = 503


class LLMReplyError(LLMError):
    """The service answered, but not with something usable."""


class LLMBudgetError(LLMUnavailableError):
    """The user has used today's calls. Raised even where there is a fallback,
    which would look like an answer and might be saved as one.
    """
    status_code = 429

    def __init__(self, limit: int):
        super().__init__(f"You've reached today's limit of {limit} AI requests. It resets at midnight UTC.")


async def require_budget(user_id) -> None:
    """Refuses, before any work starts, a user with no calls left today."""
    if not await llm_budget.has_calls_left(user_id):
        raise LLMBudgetError(llm_budget.DAILY_CALLS)


class Prompt(NamedTuple):
    system: str
    user: Any  # text, or data that is sent as JSON


T = TypeVar("T")


@dataclass(frozen=True)
class LLMReply(Generic[T]):
    value: T
    degraded: bool = False  # True when `value` came from the fallback


def build_client(**options) -> AsyncOpenAI:
    settings = {"timeout": TIMEOUT_SECONDS, "max_retries": MAX_RETRIES, **options}
    return AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY or "not-set", **settings)


client = build_client()


def clean_json_content(content: str) -> str:
    """The JSON object or array inside a reply that may wrap it in prose or
    code fences, or leave newlines unescaped inside strings.
    """
    if not content:
        return content
    content = content.strip()
    start = next((i for i, char in enumerate(content) if char in "{["), -1)
    if start == -1:
        return content
    end = content.rfind("}" if content[start] == "{" else "]")
    if end <= start:
        return content
    candidate = content[start : end + 1]
    try:
        return json.dumps(json.loads(candidate, strict=False))
    except ValueError:
        return candidate


async def chat_completion(**request):
    """The raw request. Features use `llm_json`; this exists as the single
    point where the network is touched.
    """
    response = await client.chat.completions.create(**request)
    if "response_format" in request:
        message = response.choices[0].message
        message.content = clean_json_content(message.content)
    return response


def _model_options(model: str, max_tokens: int | None) -> dict:
    reasons = "gpt-oss" in model
    options: dict = {}
    if reasons:
        # At the default effort these models often ran out of room partway
        # through the JSON.
        options["reasoning_effort"] = "low"
    if max_tokens is not None:
        options["max_tokens"] = max_tokens + (_REASONING_ALLOWANCE if reasons else 0)
    return options


def _is_rejected_json(error: Exception) -> bool:
    """The provider generated something its own JSON check refused: a bad
    reply rather than a bad request.
    """
    return isinstance(error, BadRequestError) and error.code == "json_validate_failed"


def _unavailable(error: Exception) -> LLMUnavailableError:
    if isinstance(error, RateLimitError):
        message = "The AI service has reached its usage limit. Try again in a few minutes."
    elif isinstance(error, AuthenticationError):
        message = "The AI service rejected its API key. Check GROQ_API_KEY."
    elif isinstance(error, APITimeoutError):  # before APIConnectionError, its parent
        message = "The AI service took too long to answer. Try again."
    elif isinstance(error, APIStatusError) and (
        error.status_code == 413 or error.code == "context_length_exceeded"
    ):
        message = "This text is too long for the AI service."
    elif isinstance(error, APIStatusError) and error.status_code < 500:
        message = "The AI service couldn't process this request."
    elif isinstance(error, (APIConnectionError, APIStatusError)):
        message = "The AI service is unavailable right now. Try again shortly."
    else:
        message = "The AI request failed. Try again."
    return LLMUnavailableError(message)


def _log_attempt(label: str, model: str, attempt: int, started: float, response) -> None:
    usage = getattr(response, "usage", None)
    details = getattr(usage, "completion_tokens_details", None)
    logger.info(
        "llm label=%s model=%s attempt=%d latency_ms=%d prompt_tokens=%s completion_tokens=%s "
        "reasoning_tokens=%s finish=%s",
        label, model, attempt, (time.monotonic() - started) * 1000,
        getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None),
        getattr(details, "reasoning_tokens", None),
        getattr(response.choices[0], "finish_reason", None),
    )


def _read_reply(content: str, finish_reason, schema, expect, prepare):
    """The reply as a `schema` instance. Raises ValueError (or a subclass, as
    pydantic and json do) when it can't be used.
    """
    if finish_reason == "length":
        raise ValueError("the reply stopped at the token limit")
    payload = json.loads(content)
    if not isinstance(payload, dict):
        raise ValueError("the reply is not a JSON object")
    missing = [key for key in expect if key not in payload]
    if missing:
        raise ValueError(f"the reply stopped before every section was written (no {', '.join(missing)})")
    if prepare is not None:
        payload = prepare(payload)
    return payload if schema is dict else schema.model_validate(payload)


async def llm_json(
    prompt: Prompt,
    schema: type[T],
    fallback: Callable[[], T] | None = None,
    *,
    label: str,
    expect: tuple[str, ...] = (),
    prepare: Callable[[dict], dict] | None = None,
    temperature: float = 0,
    max_tokens: int | None = None,
    model: str | None = None,
    timeout: float | None = None,
    repair: bool = False,
) -> LLMReply[T]:
    """Asks the model for a JSON object and returns it as a `schema` instance
    (a pydantic model, or `dict` for the object as it is).

    With a `fallback`, a failed call returns `fallback()` marked degraded.
    Without one it raises an `LLMError`. A user out of calls for the day gets
    `LLMBudgetError` either way.

    label       names the call in the logs
    expect      keys a finished reply always has
    prepare     adjusts the object before validation; may raise ValueError to
                reject the reply
    max_tokens  room for the answer itself
    repair      on a second attempt, show the model its reply and what was
                wrong with it, instead of simply asking again
    """
    model = model or MODEL
    user = prompt.user if isinstance(prompt.user, str) else json.dumps(prompt.user)
    messages = [{"role": "system", "content": prompt.system}, {"role": "user", "content": user}]
    failure: LLMError | None = None
    cause: Exception | None = None

    if not API_KEY:
        failure = LLMNotConfiguredError(
            "The AI service isn't set up: GROQ_API_KEY is missing. Add it to .env and restart the server."
        )
        logger.error("llm label=%s not sent: GROQ_API_KEY is not set", label)

    user_id = llm_budget.current_user.get()
    attempt = 0
    while failure is None:
        counted_on = None
        if user_id is not None and llm_budget.DAILY_CALLS > 0:
            counted_on = await llm_budget.reserve(user_id)
            if counted_on is None:
                failure = LLMBudgetError(llm_budget.DAILY_CALLS)
                logger.warning("llm label=%s not sent: user %s has no calls left today", label, user_id)
                break
        attempt += 1
        request = {
            "model": model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            **_model_options(model, max_tokens),
        }
        if timeout is not None:
            request["timeout"] = timeout

        content, started = None, time.monotonic()
        try:
            response = await chat_completion(**request)
        except Exception as e:
            logger.warning(
                "llm label=%s model=%s attempt=%d latency_ms=%d failed: %s: %s",
                label, model, attempt, (time.monotonic() - started) * 1000, type(e).__name__, e,
            )
            if not _is_rejected_json(e):
                if counted_on is not None:  # never answered, so not counted
                    await llm_budget.refund(user_id, counted_on)
                failure, cause = _unavailable(e), e
                break
            problem = e
        else:
            _log_attempt(label, model, attempt, started, response)
            content = response.choices[0].message.content or ""
            logger.debug("llm label=%s raw reply:\n%s", label, content)
            try:
                finish_reason = getattr(response.choices[0], "finish_reason", None)
                return LLMReply(_read_reply(content, finish_reason, schema, expect, prepare))
            except Exception as e:
                logger.warning("llm label=%s attempt=%d reply unusable: %s", label, attempt, e)
                problem = e

        if attempt >= _REPLY_ATTEMPTS:
            failure = LLMReplyError("The AI service returned an incomplete or unreadable answer. Try again.")
            cause = problem
        elif repair and content:
            messages = messages[:2] + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": (
                    f"That response could not be parsed/validated ({problem}). Return ONLY the corrected, "
                    "complete, valid JSON object matching the required schema — no prose, no markdown fences."
                )},
            ]
            temperature = 0

    if fallback is not None and not isinstance(failure, LLMBudgetError):
        logger.warning("llm label=%s using the fallback: %s", label, failure)
        return LLMReply(fallback(), degraded=True)
    raise failure from cause
