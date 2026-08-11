from pydantic import BaseModel


class GithubSyncRequest(BaseModel):
    username: str | None = None
    token: str | None = None


class LeetcodeSyncRequest(BaseModel):
    username: str | None = None