from pydantic import BaseModel


class LeetcodePortfolioReviewLLMOutput(BaseModel):
    """The raw structure that the LLM produces for LeetCode performance coaching."""
    interview_coach: str = ""
    learning_strategy: str = ""
    target_focus_topics: list[str] = []
    roadmap_actions: list[str] = []


class LeetcodePortfolioReviewReport(LeetcodePortfolioReviewLLMOutput):
    """The complete saved database schema representing the LLM report metadata."""
    generated_at: str = ""
    analysis_degraded: bool = False
