from pydantic import BaseModel, Field


class LeetCodeManualSubmission(BaseModel):
    """Payload for the manual fallback form (used when the unofficial
    LeetCode endpoint is broken). Keys are tag names/slugs, values are
    solved counts — e.g. {"dynamic-programming": 42, "array": 88}.
    """

    tag_counts: dict[str, int] = Field(default_factory=dict)