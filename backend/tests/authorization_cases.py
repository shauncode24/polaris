"""Every route that takes a resource ID (in the path, or as a query/body
reference to another user's data), with how to call it.

Used by two tests:
  * tests/api/test_authorization.py calls each case as a user who does NOT
    own the data and expects 404, and calls the `owner_status` cases as the
    owner to prove the route works at all (a 404 from a broken route would
    otherwise look like a pass).
  * tests/test_authorization_coverage.py fails when a new route with a path
    parameter is added without a case here, forcing an explicit decision.

Placeholders like {job_id} are filled from the seeded ids in
tests/api/conftest.py.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Case:
    method: str
    path: str
    json: dict | None = None
    # Status the owner should get, or None when calling it as the owner
    # would reach an LLM or otherwise is not a cheap, side-effect-free check.
    owner_status: int | None = None
    notes: str = field(default="", compare=False)


CASES = [
    Case("GET", "/job-intelligence/{job_id}", owner_status=200),
    Case("GET", "/jobs/by-intelligence/{job_id}"),
    Case("GET", "/job-intelligence/compare?ids={job_id}&ids={job_id}"),
    Case("PUT", "/job-intelligence/{job_id}/primary"),
    Case("DELETE", "/job-intelligence/{job_id}/primary", owner_status=200),
    Case("DELETE", "/job-intelligence/{job_id}"),
    Case("GET", "/projects/{project_id}/claim-audit", owner_status=200),
    Case("GET", "/projects/{project_id}/intelligence"),
    Case("GET", "/projects/{project_id}/interview-questions", owner_status=200),
    Case("POST", "/projects/{project_id}/link", json={"repo_name": "x"}),
    Case("POST", "/projects/{project_id}/unlink"),
    Case("GET", "/resume/tailor/{job_id}", owner_status=200),
    Case("POST", "/resume/analyze?job_intelligence_id={job_id}"),
    Case("GET", "/interview/sessions/{session_id}", owner_status=200),
    Case("POST", "/interview/correct", json={"parent_response_id": "{response_id}", "correction": "x"}),
    Case("PATCH", "/goals/{goal_id}", json={"title": "renamed"}, owner_status=200),
    Case("DELETE", "/goals/{goal_id}"),
    Case("POST", "/goals/{goal_id}/plan"),
    Case("POST", "/goals", json={"title": "t", "job_intelligence_id": "{job_id}"}),
    Case("POST", "/identity/{identity_id}/invalidate", json={"reason": "x"}),
    Case("PATCH", "/profile/projects/{project_id}", json={"action": "hide"}),
    Case("PATCH", "/profile/experiences/{experience_id}", json={"action": "hide"}),
    Case("PATCH", "/profile/education/{education_id}", json={"action": "hide"}),
]

# Routes with a path parameter that is not a reference to another user's data.
EXEMPT = {
    ("PUT", "/profile/skills/{}/visibility"): (
        "skills are shared reference data; the override is always stored for the caller, "
        "which tests/api/test_evidence.py checks"
    ),
}
