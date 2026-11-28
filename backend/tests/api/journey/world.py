"""The made-up person, job and outside services of the core journey."""
import json
import re
from datetime import datetime, timezone

from app.prompts.career_planner.career_planner import CAREER_PLANNER_SYSTEM_PROMPT
from app.prompts.interview.competency_tagging import COMPETENCY_TAGGING_SYSTEM_PROMPT
from app.prompts.interview.kit_questions import KIT_QUESTIONS_SYSTEM_PROMPT
from app.prompts.interview.practice_review import PRACTICE_REVIEW_SYSTEM_PROMPT
from app.prompts.job_intelligence.extraction import JOB_AND_COMPANY_EXTRACTION_SYSTEM_PROMPT
from app.prompts.linkedin.extraction import LINKEDIN_EXTRACTION_SYSTEM_PROMPT
from app.prompts.resume.bullet_rewriting import BULLET_REWRITE_SYSTEM_PROMPT
from app.prompts.resume.extraction import SYSTEM_PROMPT as RESUME_EXTRACTION_SYSTEM_PROMPT
from app.prompts.shared.classification import CLASSIFICATION_SYSTEM_PROMPT
from app.services.github import github_sync
from tests.llm_stub import reply

GITHUB_LOGIN = "priya-example"

ROLE_BULLETS = [
    "Built REST APIs in Python for the order service.",
    "Cut p95 latency from 800ms to 210ms by adding indexes to PostgreSQL.",
    "Led the migration of the returns flow.",
]
PROJECT_LINE = "Containerised a bookkeeping service with Docker."
RESUME_LINES = [
    "Priya Raman", "Experience", "Backend Intern, Northwind, May 2025 - Aug 2025", *ROLE_BULLETS,
    "Projects", "Ledger", PROJECT_LINE, "Education", "State University, BSc Computer Science, 2022 - 2026",
    "Skills", "Python, PostgreSQL, Docker",
]
LINKEDIN_TEXT = (
    "Teaching Assistant at State University, Aug 2024 - Apr 2025. Mentored 30 students in their Python "
    "assignments. Skills: Python."
)
JOB_TEXT = (
    "Backend Engineer at Globex. We ask for 1+ years of experience with Python, PostgreSQL, Kubernetes and "
    "algorithms. Redis is a plus. You will build and run REST APIs in Python, and design for scalability."
)

_RESUME = {
    "experiences": [{
        "role": "Backend Intern", "company": "Northwind", "start_date": "May 2025", "end_date": "Aug 2025",
        "stack": ["Python", "PostgreSQL"], "bullets": ROLE_BULLETS,
    }],
    "projects": [{"name": "Ledger", "description": PROJECT_LINE, "stack": ["Python", "Docker"]}],
    "education": [{
        "institution": "State University", "degree": "BSc", "field_of_study": "Computer Science",
        "start_date": "2022", "end_date": "2026", "details": [],
    }],
    "skills": ["Python", "PostgreSQL", "Docker"],
}
_LINKEDIN = {
    "headline": "Computer science student",
    "experience": [{
        "role": "Teaching Assistant", "company": "State University", "date_range": "Aug 2024 - Apr 2025",
        "bullets": ["Mentored 30 students in their Python assignments."],
    }],
    "education": [], "skills": ["Python"], "achievements": [],
}


def _wanted(*names) -> list[dict]:
    return [{"skill": name, "proficiency_signal": "not_specified"} for name in names]


_JOB = {
    "job": {
        "role": "Backend Engineer", "company": "Globex",
        "required_skills": _wanted("Python", "PostgreSQL", "Kubernetes", "Algorithms"),
        "implicit_skills": [], "nice_to_have": _wanted("Redis"),
        "architecture_topics": ["Scalability"], "responsibilities": ["Build and run REST APIs in Python"],
        "qualification_requirements": {"education": [], "eligibility": [], "experience": None},
    },
    "company": {},
}


class StandInModel:
    """Answers each kind of request as a well-behaved model would, and records
    which kinds it answered. Anything else fails, as an unreachable model does.
    """

    def __init__(self):
        self.answered: set[str] = set()
        self._answers = {
            RESUME_EXTRACTION_SYSTEM_PROMPT: ("resume_extraction", lambda _asked: _RESUME),
            LINKEDIN_EXTRACTION_SYSTEM_PROMPT: ("linkedin_extraction", lambda _asked: _LINKEDIN),
            JOB_AND_COMPANY_EXTRACTION_SYSTEM_PROMPT: ("job_extraction", lambda _asked: _JOB),
            CLASSIFICATION_SYSTEM_PROMPT: ("skill_classification", lambda asked: {"results": [
                {"raw": raw, "canonical": None, "is_valid_skill": False} for raw in asked]}),
            BULLET_REWRITE_SYSTEM_PROMPT: ("bullet_rewrite", lambda asked: {
                "rewrite": f"Delivered: {asked['bullet']}"}),
            COMPETENCY_TAGGING_SYSTEM_PROMPT: ("competency_tagging", lambda asked: {"results": [
                {"key": item["key"], "tags": ["ownership"]} for item in asked]}),
            KIT_QUESTIONS_SYSTEM_PROMPT: ("kit_questions", lambda asked: {"questions": [
                {"id": q["id"], "question": f"Thinking of {q['topic']}, how would you approach it?"}
                for q in asked["questions"]]}),
            PRACTICE_REVIEW_SYSTEM_PROMPT: ("practice_review", self._review),
            CAREER_PLANNER_SYSTEM_PROMPT: ("career_plan", lambda asked: {"daily_plan": [
                {"day": day, "theme": f"Day {day}", "tasks": ["Solve a LeetCode Sliding Window problem."]}
                for day in asked["assigned_days"]]}),
        }

    @staticmethod
    def _review(asked: dict) -> dict:
        words = re.findall(r"\S+", asked["answer"])
        return {"headings": [
            {"heading": h["heading"], "covered": number < 2, "quote": " ".join(words[:4]) if number < 2 else "",
             "note": "Say a little more."}
            for number, h in enumerate(asked["headings"])
        ], "overall": "Add the decisions you weighed."}

    async def __call__(self, **request):
        system, user = request["messages"][0]["content"], request["messages"][1]["content"]
        if system not in self._answers:
            raise ConnectionError("the stand-in model has no answer for this")
        name, answer = self._answers[system]
        try:
            asked = json.loads(user)
        except ValueError:
            asked = user  # some requests send plain text
        self.answered.add(name)
        return reply(answer(asked))


def leetcode_profile() -> dict:
    counts = {"array": 30, "dynamic-programming": 12, "binary-search": 4}
    return {
        "tag_counts": counts, "tag_difficulty_tier": {}, "total_solved": 46, "easy": 30, "medium": 14, "hard": 2,
        "contest_rating": None, "global_ranking": None, "attended_contests_count": 0, "active_days_last_30": 6,
        "submissions_last_30": 11, "longest_streak": 3, "current_streak": 1, "longest_gap_days": 9,
    }


def stand_in_github(setattr_) -> None:
    """Two repositories: the resume's project, and one the resume leaves out."""
    def returns(value):
        async def call(*args, **kwargs):
            return value
        return call

    async def last_commit(client, username, repo_name, token):
        return {"sha": f"sha-{repo_name}", "date": datetime.now(timezone.utc)}

    for name, value in {
        "fetch_repos": [{"name": "ledger", "description": "A bookkeeping service"}, {"name": "campus-map"}],
        "fetch_languages": {"Python": 100}, "fetch_commit_count_last_30d": 3, "fetch_readme_exists": True,
        "fetch_ci_config_exists": True, "fetch_repo_tree": ["app/main.py", "tests/test_main.py"],
        "fetch_repo_file": None, "fetch_repo_path_exists": False, "fetch_recent_commits": [],
        "fetch_pull_request_stats": {}, "fetch_user_commit_count_capped": 0,
    }.items():
        setattr_(github_sync, name, returns(value))
    setattr_(github_sync, "fetch_last_commit_info", last_commit)
    setattr_(github_sync, "is_eligible_for_architecture_pass", lambda **kwargs: False)
