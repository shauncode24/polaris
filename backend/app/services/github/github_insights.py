"""Turns per-repo sync data into career-facing insights — 'what does
this say about me as an engineer', not 'what exists on GitHub'. Every
field here should be directly consumable by Resume Reviewer, Skill Gap
Analyzer, Career Planner, Interview Response Agent, or Progress
Tracker. If a field is just GitHub metadata in a nicer shape, it
belongs in the raw snapshot, not here.
"""
from datetime import datetime, timezone


def build_repo_headline(repo: dict) -> str:
    """One synthesized sentence per repo so the explorer stops reading
    like a repeated data table. Every clause is a real, checked fact —
    never invented. Deterministic, same philosophy as the rest of this
    file: no LLM call, just prioritized templating.
    """
    if repo.get("is_fork") and repo.get("is_meaningful_fork_contribution") is False:
        return "Fork — no significant original contribution detected"

    strengths, gaps = [], []
    if repo.get("has_readme"):
        strengths.append("well documented")
    else:
        gaps.append("missing README")
    if repo.get("has_tests"):
        strengths.append("tested")
    else:
        gaps.append("no tests")
    if repo.get("has_ci"):
        strengths.append("has CI")
    else:
        gaps.append("no CI")

    score = repo.get("project_score", {}).get("overall", 0)
    lead = "Strong architecture" if score >= 70 else ("Solid foundation" if score >= 45 else "Early stage")

    parts = []
    if strengths:
        parts.append(", ".join(strengths[:2]).capitalize())
    if gaps:
        parts.append(f"needs {gaps[0]}" if len(gaps) == 1 else f"needs {', '.join(gaps[:2])}")

    return f"{lead} — " + "; ".join(parts) if parts else lead


def build_ranked_recommendations(repositories: list[dict]) -> list[dict]:
    """Estimates the score-point gain from fixing the single biggest gap
    on each repo, using the exact same weights as github_scoring.py so
    the number shown is never fabricated — it's a real delta of that
    formula. Sorted descending so 'highest ROI' is genuinely highest ROI.
    Skips forks with no real contribution — there's nothing to recommend
    improving on someone else's code.
    """
    candidates = []
    for r in repositories:
        if r.get("is_fork") and r.get("is_meaningful_fork_contribution") is False:
            continue

        breakdown = r.get("project_score", {}).get("breakdown", {})
        if not r.get("has_readme"):
            candidates.append({"project": r["name"], "action": f"Write a README for {r['name']}", "impact": 10})
        if not r.get("has_tests"):
            candidates.append({"project": r["name"], "action": f"Add tests to {r['name']}", "impact": 15})
        if not r.get("has_ci"):
            candidates.append({"project": r["name"], "action": f"Add CI to {r['name']}", "impact": 10})
        if r.get("archived") is False and r.get("commits_last_30_days", 0) == 0 and breakdown.get("activity", 0) < 5:
            candidates.append({"project": r["name"], "action": f"Archive or resume {r['name']}", "impact": 4})

        hygiene = r.get("commit_hygiene") or {}
        if hygiene.get("sample_size", 0) >= 5 and hygiene.get("score", 100) < 40:
            candidates.append({
                "project": r["name"],
                "action": f"Write clearer, more specific commit messages for {r['name']}",
                "impact": 6,
            })

    candidates.sort(key=lambda c: c["impact"], reverse=True)
    return candidates[:6]


def build_github_insights(
    repositories: list[dict],
    scores: dict[str, int],
    tech_distribution: dict[str, dict[str, int]],
    total_language_bytes: dict[str, int],
    prev_insights: dict | None = None,
) -> dict:
    total = len(repositories) or 1
    category_counts = {cat: sum(techs.values()) for cat, techs in tech_distribution.items()}

    # 1. Portfolio Profile (Domains and Project Types)
    domains = []
    if category_counts.get("frontend", 0) > 0 or category_counts.get("backend", 0) > 0 or category_counts.get("databases", 0) > 0:
        domains.append("Web Applications")
    if category_counts.get("ai", 0) > 0:
        domains.append("AI Applications")
    if category_counts.get("mobile", 0) > 0:
        domains.append("Mobile Applications")
    if category_counts.get("devops", 0) > 0:
        domains.append("Cloud & Infrastructure")
    if category_counts.get("testing", 0) > 0:
        domains.append("Test Engineering")
    if not domains and category_counts.get("languages", 0) > 0:
        domains.append("Developer Tools")

    project_types_set = set()
    for repo in repositories:
        langs = {l.lower() for l in repo.get("languages", [])}
        topics = {t.lower() for t in repo.get("topics", [])}

        has_frontend = any(l in {"javascript", "typescript", "html", "css"} for l in langs) or any(
            t in {"react", "vue", "angular", "svelte", "nextjs", "tailwind"} for t in topics
        )
        has_backend = any(l in {"python", "go", "rust", "c#", "java", "php", "ruby"} for l in langs) or any(
            t in {"fastapi", "django", "flask", "express", "nodejs", "spring"} for t in topics
        )

        if has_frontend and has_backend:
            project_types_set.add("Full Stack")
        elif has_backend:
            project_types_set.add("Backend APIs")
        elif has_frontend:
            project_types_set.add("Frontend Web")
        else:
            project_types_set.add("Automation & Libraries")

    project_types = sorted(list(project_types_set))

    # 2. Engineering Habits / Practices
    repos_with_readme = sum(1 for r in repositories if r.get("has_readme"))
    doc_score = round((repos_with_readme / total) * 100)

    repos_with_tests = sum(1 for r in repositories if r.get("has_tests"))
    test_score = round((repos_with_tests / total) * 100)

    docker_count = sum(
        1
        for r in repositories
        if any("docker" in t.lower() for t in r.get("topics", []))
        or (r.get("description") and "docker" in r["description"].lower())
    )
    ci_count = sum(1 for r in repositories if r.get("has_ci"))

    active_projects = sum(1 for r in repositories if r.get("commits_last_30_days", 0) > 0)
    stale_projects = len(repositories) - active_projects

    hygiene_scores = [r["commit_hygiene"]["score"] for r in repositories if (r.get("commit_hygiene") or {}).get("sample_size", 0) > 0]
    avg_hygiene_score = round(sum(hygiene_scores) / len(hygiene_scores)) if hygiene_scores else None

    collaborative_repos = sum(1 for r in repositories if (r.get("collaboration") or {}).get("mode") in ("collaborative", "mixed"))

    # 3. Progress and Trends
    dominant_languages = [
        lang for lang, _ in sorted(total_language_bytes.items(), key=lambda kv: kv[1], reverse=True)[:2]
    ]
    recent_focus = dominant_languages[0] if dominant_languages else "None"

    backend_activity = "Unchanged"
    documentation_trend = "Unchanged"
    testing_trend = "Unchanged"
    new_technologies = []

    if prev_insights:
        prev_backend_count = sum(prev_insights.get("technology_distribution", {}).get("backend", {}).values())
        curr_backend_count = sum(tech_distribution.get("backend", {}).values())
        if curr_backend_count > prev_backend_count:
            backend_activity = "Increasing"
        elif curr_backend_count < prev_backend_count:
            backend_activity = "Decreasing"

        prev_doc_score = prev_insights.get("engineering_practices", {}).get("documentation", {}).get("score", 0)
        if doc_score > prev_doc_score:
            documentation_trend = "Improving"
        elif doc_score < prev_doc_score:
            documentation_trend = "Declining"

        prev_test_score = prev_insights.get("engineering_practices", {}).get("testing", {}).get("score", 0)
        if test_score > prev_test_score:
            testing_trend = "Improving"
        elif test_score < prev_test_score:
            testing_trend = "Declining"

        curr_techs = set()
        for techs in tech_distribution.values():
            curr_techs.update(techs.keys())

        prev_techs = set()
        for techs in prev_insights.get("technology_distribution", {}).values():
            prev_techs.update(techs.keys())

        new_technologies = sorted(list(curr_techs - prev_techs))

    # 4. Recommendations
    recommendations = build_ranked_recommendations(repositories)

    # Softer, non-absolute observations for strengths
    strengths_list = []
    if category_counts.get("frontend", 0) >= 2 or any(lang.lower() in {"javascript", "typescript"} for lang in dominant_languages):
        strengths_list.append("Portfolio contains multiple frontend applications demonstrating sustained JavaScript/TypeScript usage.")
    if category_counts.get("backend", 0) >= 2:
        strengths_list.append("Portfolio features backend services demonstrating API design.")
    if category_counts.get("databases", 0) >= 2:
        strengths_list.append("Portfolio includes implementations leveraging database technologies.")
    if category_counts.get("ai", 0) > 0:
        strengths_list.append("Portfolio includes applications with integrated AI/ML components.")
    if collaborative_repos > 0:
        strengths_list.append(f"{collaborative_repos} repositories show real PR/review collaboration, not just solo commits.")

    return {
        "portfolio_profile": {
            "domains": domains,
            "project_types": project_types,
        },
        "engineering_practices": {
            "documentation": {
                "score": doc_score,
                "repos_with_readme": repos_with_readme,
            },
            "testing": {
                "score": test_score,
                "repos_with_tests": repos_with_tests,
            },
            "devops": {
                "docker": docker_count,
                "ci": ci_count,
            },
            "maintenance": {
                "active_projects": active_projects,
                "stale_projects": stale_projects,
            },
            "commit_hygiene": {
                "average_score": avg_hygiene_score,
            },
            "collaboration": {
                "collaborative_or_mixed_repos": collaborative_repos,
            },
        },
        "progress": {
            "recent_focus": recent_focus,
            "backend_activity": backend_activity,
            "documentation": documentation_trend,
            "testing": testing_trend,
            "new_technologies": new_technologies,
        },
        "recommendations": recommendations,
        "technology_distribution": tech_distribution,
        "strengths": strengths_list,
    }