"""A stand-in for the model: tests queue the replies or errors it should give."""
import json

import httpx
import pytest

from app.core import llm


def reply(content, finish_reason="stop"):
    """A response shaped like the client library's."""
    if not isinstance(content, str):
        content = json.dumps(content)
    message = type("Message", (), {"content": content})()
    choice = type("Choice", (), {"message": message, "finish_reason": finish_reason})()
    return type("Response", (), {"choices": [choice], "usage": None})()


def api_error(kind, status: int, code: str | None = None):
    response = httpx.Response(status, request=httpx.Request("POST", "http://llm.invalid"))
    return kind("provider detail that users must not see", response=response, body={"code": code})


class StubModel:
    def __init__(self):
        self.queue: list = []
        self.requests: list[dict] = []

    def will(self, *items):
        """Each item is a response (`reply(...)`), a reply body, or an error."""
        self.queue.extend(items)

    async def __call__(self, **request):
        self.requests.append(request)
        item = self.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item if hasattr(item, "choices") else reply(item)


@pytest.fixture
def model(monkeypatch):
    stub = StubModel()
    monkeypatch.setattr(llm, "chat_completion", stub)
    return stub
