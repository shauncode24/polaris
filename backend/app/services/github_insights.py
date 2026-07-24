"""Turns per-repo sync data into career-facing insights — 'what does
this say about me as an engineer', not 'what exists on GitHub'. Every
field here should be directly consumable by Resume Reviewer, Skill Gap
Analyzer, Career Planner, Interview Response Agent, or Progress
Tracker. If a field is just GitHub metadata in a nicer shape, it
belongs in the raw snapshot, not here.
"""
from datetime import datetime, timezone

NEGLECT_THRESHOLD_DAYS = 60
MAX_NEGLECTED = 5
MAX_STRONGEST = 5
MAX_ACTIVE = 10


def _days_since(pushed_at: str | None) -> int | None:
    if not pushed_at:
        return None
    pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - pushed).days


def _neglect_reason(repo: dict, score: int) -> str:
    """Template-based, not LLM-generated — deterministic and free to run
    on every sync, for every repo."""
    if score >= 60:
        return "High-scoring project with no recent activity — a strong candidate to resume."
    if not repo.get("has_readme") or not repo.get("description"):
        return "Portfolio project that could benefit from documentation and a description."
    if repo.get("stars", 0) + repo.get("forks", 0) > 0:
        return "Has external interest (stars/forks) but has gone quiet."
    return "Idle project — consider finishing, documenting, or archiving it."


def _category_label(category: str) -> str:
    return {
        "frontend": "Frontend Development", "backend": "Backend Development",
        "databases": "Database Engineering", "devops": "DevOps",
        "ai": "AI Applications", "mobile": "Mobile Development",
        "testing": "Test Engineering", "languages": "General Software Development",
    }.get(category, category.title())


def build_github_insights(
    repositories: list[dict],
    scores: dict[str, int],
    tech_distribution: dict[str, dict[str, int]],
    total_language_bytes: dict[str, int],
) -> dict:
    non_archived = [r for r in repositories if not r.get("archived")]
    total = len(repositories) or 1

    active_projects = [
        r["name"] for r in sorted(
            (r for r in repositories if r.get("commits_last_30_days", 0) > 0),
            key=lambda r: r["commits_last_30_days"], reverse=True,
        )[:MAX_ACTIVE]
    ]

    strongest_projects = [
        {"name": r["name"], "score": scores.get(r["name"], 0)}
        for r in sorted(repositories, key=lambda r: scores.get(r["name"], 0), reverse=True)[:MAX_STRONGEST]
    ]

    neglect_candidates = []
    for r in non_archived:
        days = _days_since(r.get("pushed_at"))
        if r.get("commits_last_30_days", 0) == 0 and days is not None and days > NEGLECT_THRESHOLD_DAYS:
            neglect_candidates.append((r, days))
    neglect_candidates.sort(key=lambda pair: scores.get(pair[0]["name"], 0), reverse=True)

    neglected_projects = [
        {"name": r["name"], "last_commit_days": days, "reason": _neglect_reason(r, scores.get(r["name"], 0))}
        for r, days in neglect_candidates[:MAX_NEGLECTED]
    ]

    category_counts = {cat: sum(techs.values()) for cat, techs in tech_distribution.items()}
    ranked_categories = sorted(category_counts.items(), key=lambda kv: kv[1], reverse=True)
    primary_focus = _category_label(ranked_categories[0][0]) if ranked_categories else "Unclear"
    secondary_focus = _category_label(ranked_categories[1][0]) if len(ranked_categories) > 1 else None
    dominant_languages = [
        lang for lang, _ in sorted(total_language_bytes.items(), key=lambda kv: kv[1], reverse=True)[:2]
    ]

    tested_count = sum(1 for r in repositories if r.get("has_tests"))
    ci_count = sum(1 for r in repositories if r.get("has_ci"))
    readme_count = sum(1 for r in repositories if r.get("has_readme"))

    experience_level = (
        "Advanced" if len(non_archived) >= 15 and tested_count / total > 0.3
        else "Intermediate" if len(non_archived) >= 5
        else "Early"
    )

    strengths: list[str] = []
    for category, _ in ranked_categories[:2]:
        top_tech = max(tech_distribution[category].items(), key=lambda kv: kv[1], default=None)
        if top_tech:
            strengths.append(f"Strong {top_tech[0]} portfolio ({top_tech[1]} repositories)")
    if category_counts.get("ai", 0) > 0:
        strengths.append("Growing AI/ML project experience")
    if len(tech_distribution.get("databases", {})) >= 2:
        strengths.append("Comfortable across multiple database technologies")

    gaps: list[str] = []
    if tested_count / total < 0.2:
        gaps.append("Very little automated testing across repositories")
    if ci_count / total < 0.2:
        gaps.append("Few projects with CI/CD configured")
    if readme_count / total < 0.5:
        gaps.append("Many repositories lack documentation")
    if not any(r.get("stars", 0) + r.get("forks", 0) > 3 for r in repositories):
        gaps.append("No large collaborative open-source contributions")

    return {
        "active_projects": active_projects,
        "strongest_projects": strongest_projects,
        "neglected_projects": neglected_projects,
        "technology_distribution": tech_distribution,
        "engineering_profile": {
            "primary_focus": primary_focus,
            "secondary_focus": secondary_focus,
            "experience_level": experience_level,
            "dominant_languages": dominant_languages,
        },
        "strengths": strengths,
        "gaps": gaps,
    }