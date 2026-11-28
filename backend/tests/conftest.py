"""Test environment.

This module runs before any test imports the app, so it decides which
database the app's settings will point at.

* If TEST_DATABASE_URL is set, the app uses it. Database-backed tests run
  against it, and the schema is dropped and rebuilt from the migrations, so
  the database name must contain "test".
* If it is not set, DATABASE_URL is forced to a local placeholder. The real
  DATABASE_URL in .env is never used by the test suite, and database-backed
  tests are skipped.
"""
import os
from urllib.parse import urlparse

import httpx
import pytest
from cryptography.fernet import Fernet

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if TEST_DATABASE_URL:
    database_name = urlparse(TEST_DATABASE_URL).path.lstrip("/")
    if "test" not in database_name:
        raise RuntimeError(
            f"Refusing to run tests against database '{database_name}': TEST_DATABASE_URL must "
            f"point at a database whose name contains 'test', because the test run drops its schema."
        )
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
else:
    os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/polaris_unavailable"

# Tests never reach a real model: whatever .env holds is overridden, so a call
# a test forgot to stub fails at once instead of spending the account's quota.
os.environ["GROQ_API_KEY"] = "test-key-never-sent"
os.environ["GROQ_BASE_URL"] = "http://llm.invalid/v1"
os.environ["GROQ_MODEL"] = "openai/gpt-oss-120b"
os.environ["LLM_MAX_RETRIES"] = "0"
# Tests reuse a few users far beyond a real day's use; the limit has its own tests.
os.environ["LLM_DAILY_CALLS_PER_USER"] = "100000"

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
# Every test request comes from one client, far faster than any real user. The
# limits have their own tests.
for name in ("RATE_LIMIT_REQUESTS", "AUTH_RATE_LIMIT_REQUESTS", "AI_RATE_LIMIT_REQUESTS"):
    os.environ[name] = "100000"
os.environ["TRUSTED_PROXIES"] = ""
# Sessions behave the same whatever .env holds.
os.environ["FRONTEND_ORIGIN"] = "http://localhost:5173"
os.environ["COOKIE_SAMESITE"] = "lax"
os.environ["ACCESS_TOKEN_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_DAYS"] = "14"

# Database-backed tests live under tests/api and need a real Postgres.
collect_ignore = [] if TEST_DATABASE_URL else ["api"]


@pytest.fixture(autouse=True)
def offline_model(monkeypatch):
    """A model call nobody stubbed fails immediately, without touching the
    network.
    """
    from app.core import llm

    def refuse(request):
        raise httpx.ConnectError("tests don't call the model", request=request)

    monkeypatch.setattr(llm, "client", llm.build_client(
        max_retries=0, http_client=httpx.AsyncClient(transport=httpx.MockTransport(refuse)),
    ))
