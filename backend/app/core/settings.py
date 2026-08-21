import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")


class ConfigurationError(RuntimeError):
    """Raised at startup when a required environment variable is missing
    or malformed. Phase 1 security baseline (§1.4): previously several
    of these silently fell back to an insecure default (JWT_SECRET =
    "dev-secret-change-me") or failed with a raw, unhelpful KeyError
    (DATABASE_URL) instead of a clear, actionable message. Every
    required secret now fails fast, on startup, with an explanation.
    """


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigurationError(
            f"Required environment variable '{name}' is not set. Refusing to start with a "
            f"missing/insecure default — set it in your .env file or environment."
        )
    return value


class Settings:
    def __init__(self) -> None:
        raw_url = _require_env("DATABASE_URL")

        if raw_url.startswith("postgresql://"):
            raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        parsed = urlparse(raw_url)
        query_params = parse_qs(parsed.query)

        self.connect_args = {}

        if "sslmode" in query_params:
            sslmode = query_params.pop("sslmode")[0]
            if sslmode in ("require", "verify-ca", "verify-full"):
                self.connect_args["ssl"] = True

        new_query = urlencode(query_params, doseq=True)
        self.database_url = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )

        # --- Phase 3: sync credentials ---
        self.github_token = os.environ.get("GITHUB_TOKEN", "")
        self.github_username = os.environ.get("GITHUB_USERNAME", "")
        self.leetcode_username = os.environ.get("LEETCODE_USERNAME", "")

        # --- Auth ---
        # SECURITY FIX (Phase 1 §1.4): JWT_SECRET is now REQUIRED — no
        # hardcoded "dev-secret-change-me" fallback. A missing value now
        # fails the app at startup instead of silently signing tokens
        # with a well-known, publicly-visible secret.
        self.jwt_secret = _require_env("JWT_SECRET")
        self.jwt_algorithm = "HS256"
        self.jwt_expire_minutes = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))  # 7 days
        self.google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")

        # --- Encryption at rest (Phase 1 §1.4) ---
        # Used to encrypt sensitive third-party credentials stored on the
        # User row (currently: GitHub personal access tokens) before they
        # ever reach the database — see core/security.py's
        # encrypt_secret/decrypt_secret and api/sync.py. Required, same
        # fail-fast policy as JWT_SECRET: there is no safe default for a
        # symmetric encryption key. Generate one with:
        #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
        self.encryption_key = _require_env("ENCRYPTION_KEY")

        # --- Input-size / abuse limits (Phase 1 §1.4) ---
        self.max_upload_bytes = int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))  # 10 MB
        self.max_paste_text_chars = int(os.environ.get("MAX_PASTE_TEXT_CHARS", "50000"))
        self.max_request_body_bytes = int(os.environ.get("MAX_REQUEST_BODY_BYTES", str(15 * 1024 * 1024)))

        # --- Rate limiting (Phase 1 §1.4) ---
        self.rate_limit_requests = int(os.environ.get("RATE_LIMIT_REQUESTS", "120"))
        self.rate_limit_window_seconds = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))

        # --- Observability (Phase 1 §1.1) ---
        # Controls the root logger level set by app/core/logging_config.py.
        # Use LOG_LEVEL=DEBUG locally to surface raw LLM payloads.
        # Defaults to INFO in all other environments.
        self.log_level = os.environ.get("LOG_LEVEL", "INFO").upper()


settings = Settings()