"""Per-technology DEPTH scoring — answers "how deep does this person's
experience with X actually go", not just "have they touched X at all".
categorize_technologies() in github_taxonomy.py already answers breadth
("used in N repos"); this module is the missing proficiency signal: a
user who touched FastAPI once in a tutorial-shaped repo and a user
who's iterated on FastAPI across five increasingly complex,
well-architected repos were previously treated identically. Depth
combines recency + repo count + architecture depth + commit hygiene
into one explainable 0-100 score per technology.

Deterministic only — no LLM. Same philosophy as github_scoring.py.
"""

MAX_SCORE = 100

# architecture_assessment.depth_label -> points (0-100 scale component)
DEPTH_LABEL_POINTS = {
    "flat_script": 10,
    "basic_structure": 40,
    "layered": 75,
    "well_architected": 100,
}
DEFAULT_DEPTH_LABEL_POINTS = 25  # no architecture assessment available for this repo

DEPTH_LABELS = [
    (80, "Deep expertise"),
    (55, "Working proficiency"),
    (30, "Applied exposure"),
    (0, "Surface-level"),
]


def _label_for_score(score: float) -> str:
    for floor, label in DEPTH_LABELS:
        if score >= floor:
            return label
    return "Surface-level"


def compute_technology_depth(repos_using_tech: list[dict]) -> dict:
    """`repos_using_tech`: list of {"last_activity_days": int|None,
    "commit_hygiene_score": float, "architecture_depth_label": str|None,
    "quality_score": float}, one entry per eligible (non-thin-fork) repo
    that uses this technology.

    Returns {"score": int, "label": str, "repo_count": int, "breakdown": {...}}.
    """
    repo_count = len(repos_using_tech)
    if repo_count == 0:
        return {"score": 0, "label": "No evidence", "repo_count": 0, "breakdown": {}}

    # Breadth (0-25): more repos using this tech = more reinforced
    # evidence, capped so 5+ repos doesn't keep climbing forever.
    breadth = min(repo_count, 5) / 5 * 25

    # Recency (0-25): the most-recently-touched repo using this tech,
    # decaying smoothly to 0 past ~365 days idle.
    recencies = [r.get("last_activity_days") for r in repos_using_tech if r.get("last_activity_days") is not None]
    recency = max(0.0, 25.0 - (min(recencies) / 365 * 25)) if recencies else 0.0

    # Architecture depth (0-30): the STRONGEST architecture read among
    # repos using this tech — one well-architected repo is meaningful
    # evidence of depth even if other repos using the same tech are simpler.
    # Intentional: max, not average — revisit with repo-count weighting if
    # this proves too lenient in practice.
    depth_points = [
        DEPTH_LABEL_POINTS.get(r.get("architecture_depth_label"), DEFAULT_DEPTH_LABEL_POINTS)
        for r in repos_using_tech
    ]
    architecture = (max(depth_points) / 100) * 30

    # Commit hygiene (0-20): average hygiene across repos using this tech.
    hygiene_scores = [r.get("commit_hygiene_score", 0.0) for r in repos_using_tech]
    hygiene = (sum(hygiene_scores) / len(hygiene_scores) / 100) * 20 if hygiene_scores else 0.0

    score = round(min(breadth + recency + architecture + hygiene, MAX_SCORE))

    return {
        "score": score,
        "label": _label_for_score(score),
        "repo_count": repo_count,
        "breakdown": {
            "breadth": round(breadth),
            "recency": round(recency),
            "architecture": round(architecture),
            "commit_hygiene": round(hygiene),
        },
    }


def build_technology_depth_map(repositories: list[dict]) -> dict[str, dict]:
    """`repositories`: eligible (non-thin-fork) repo dicts each with
    "technologies", "last_activity_days", "commit_hygiene_score", and
    "architecture_assessment": {"depth_label": ...} or None.

    Returns {technology_name: depth_result}, one entry per technology
    that appears in at least one eligible repo.
    """
    by_tech: dict[str, list[dict]] = {}
    for repo in repositories:
        hygiene_score = repo.get("commit_hygiene_score")
        if hygiene_score is None:
            hygiene_score = (repo.get("commit_hygiene") or {}).get("score", 0.0)
        arch = repo.get("architecture_assessment") or {}
        entry = {
            "last_activity_days": repo.get("last_activity_days"),
            "commit_hygiene_score": hygiene_score,
            "architecture_depth_label": arch.get("depth_label"),
            "quality_score": repo.get("quality_score", 0.0),
        }
        for tech in repo.get("technologies", []) or []:
            by_tech.setdefault(tech, []).append(entry)

    return {tech: compute_technology_depth(repos) for tech, repos in by_tech.items()}