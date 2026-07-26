import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")


class Settings:
    def __init__(self) -> None:
        raw_url = os.environ["DATABASE_URL"]

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
        self.jwt_secret = os.environ.get("JWT_SECRET", "dev-secret-change-me")
        self.jwt_algorithm = "HS256"
        self.jwt_expire_minutes = int(os.environ.get("JWT_EXPIRE_MINUTES", "10080"))  # 7 days
        self.google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")

settings = Settings()