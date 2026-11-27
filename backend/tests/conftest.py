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

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("ENCRYPTION_KEY", Fernet.generate_key().decode())
# Every test request comes from one client, far faster than any real user.
os.environ.setdefault("RATE_LIMIT_REQUESTS", "100000")

# Database-backed tests live under tests/api and need a real Postgres.
collect_ignore = [] if TEST_DATABASE_URL else ["api"]
