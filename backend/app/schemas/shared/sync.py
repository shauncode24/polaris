from pydantic import BaseModel, field_validator

MAX_USERNAME_LEN = 100
MAX_TOKEN_LEN = 255


def _validate_username(v: str | None, field_name: str) -> str | None:
    if v is None:
        return v
    stripped = v.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank if provided.")
    if len(stripped) > MAX_USERNAME_LEN:
        raise ValueError(f"{field_name} must be {MAX_USERNAME_LEN} characters or fewer.")
    return stripped


class GithubSyncRequest(BaseModel):
    username: str | None = None
    token: str | None = None

    # SECURITY FIX (Phase 1 §1.4 — validate external API inputs):
    # previously unbounded strings were passed straight through to the
    # GitHub API client with no shape/length check at all.
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        return _validate_username(v, "username")

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: str | None) -> str | None:
        if v is None:
            return v
        stripped = v.strip()
        if not stripped:
            raise ValueError("token must not be blank if provided.")
        if len(stripped) > MAX_TOKEN_LEN:
            raise ValueError(f"token must be {MAX_TOKEN_LEN} characters or fewer.")
        return stripped


class LeetcodeSyncRequest(BaseModel):
    username: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        return _validate_username(v, "username")