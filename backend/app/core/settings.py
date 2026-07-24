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


settings = Settings()