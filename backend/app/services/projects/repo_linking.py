"""Deterministic repo-to-project linkage. Name-only matching (the
original approach) silently drops GitHub-verified signal whenever a
resume project's name doesn't equal the repo name exactly (e.g. "Cortex
Route" vs "cortex-route-gateway"). This module fixes that by trying, in
order:

1. Exact repo_url-derived name match
2. Normalized-slug exact name match
3. Fuzzy substring slug match, either direction

Every match is still 100% deterministic — no LLM, no embeddings. Same
"cheap and explainable" philosophy as skill_categories.py and
github_taxonomy.py elsewhere in this codebase.
"""
import re

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    return _SLUG_STRIP_RE.sub("", text.lower())


def _repo_name_from_url(url: str | None) -> str | None:
    if not url:
        return None
    cleaned = url.rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[: -len(".git")]
    parts = cleaned.split("/")
    return parts[-1] if parts else None


def match_project_to_repo(project_name: str, project_repo_url: str | None, repo_names: list[str]) -> str | None:
    """Returns the matched repo_name, or None. `repo_names` are the real
    synced GitHub repo names for this user (GithubProjectAnalysis.repo_name
    values).
    """
    if not repo_names:
        return None

    # 1. repo_url-derived name — most reliable signal we have.
    url_repo_name = _repo_name_from_url(project_repo_url)
    if url_repo_name:
        url_slug = _slugify(url_repo_name)
        for repo_name in repo_names:
            if _slugify(repo_name) == url_slug:
                return repo_name

    # 2. exact slug match on the project's own name
    project_slug = _slugify(project_name)
    if project_slug:
        for repo_name in repo_names:
            if _slugify(repo_name) == project_slug:
                return repo_name

    # 3. substring slug match, either direction — catches
    # "Cortex Route" vs "cortex-route-gateway"
    for repo_name in repo_names:
        repo_slug = _slugify(repo_name)
        if not repo_slug or not project_slug:
            continue
        if repo_slug in project_slug or project_slug in repo_slug:
            return repo_name

    return None


def build_repo_lookup(analysis_by_repo_name: dict, projects: list) -> dict:
    """project.id -> repo_name, for every project that matches a synced
    repo under any of the three tiers above. Computed once per overview
    build (repo_names list built once) instead of once per project.
    """
    repo_names = list(analysis_by_repo_name.keys())
    lookup: dict = {}
    for p in projects:
        matched = match_project_to_repo(p.name, p.repo_url, repo_names)
        if matched:
            lookup[p.id] = matched
    return lookup