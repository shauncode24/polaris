"""Resume Analysis Engine — Orchestrator.

Runs all 7 analysis modules against the user's latest resume,
aggregates the scores, generates suggestions, and persists the result
as a ResumeAnalysis row.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facts import Experience, Project, Education, JobDescription, Resume, GithubSnapshot, LeetcodeSnapshot, Certificate
from app.models.structure import Skill
from app.models.inference import ResumeAnalysis

from app.services.resume.analysis.structure   import analyze_structure
from app.services.resume.analysis.parsing     import analyze_parsing
from app.services.resume.analysis.formatting  import analyze_formatting
from app.services.resume.analysis.content     import analyze_content
from app.services.resume.analysis.metrics     import analyze_metrics
from app.services.resume.analysis.keywords    import analyze_keywords
from app.services.resume.analysis.evidence    import analyze_evidence
from app.services.resume.analysis.scoring     import get_grade, get_label, get_grade_color
from app.services.resume.analysis.suggestions import generate_suggestions


EXCLUDED_SKILLS = {
    "array", "string", "hash table", "sorting", "math", "two pointers",
    "stack", "greedy", "binary search", "matrix", "monotonic stack",
    "heap (priority queue)", "divide and conquer", "bit manipulation", "trie",
    "sliding window", "recursion", "backtracking", "simulation", "merge sort",
    "quickselect", "bucket sort", "counting", "radix sort", "counting sort",
    "ordered set", "prefix sum", "hash function", "two-pointers", "heap",
    "binary tree", "tree", "depth-first search", "breadth-first search", "dfs", "bfs",
    "graph", "dynamic programming", "memoization", "design",
    "interactive", "database", "linked list", "doubly-linked list", "combinatorics"
}


def _collect_bullets(experiences: list, projects: list) -> list[str]:
    bullets: list[str] = []
    for exp in experiences:
        for b in (exp.bullets or []):
            stripped = b.strip()
            if stripped:
                bullets.append(stripped)
    for proj in projects:
        if proj.description:
            for line in proj.description.split("\n"):
                stripped = line.strip("-•*▪ \t")
                if len(stripped) > 10:
                    bullets.append(stripped)
    return bullets


async def run_analysis(
    db: AsyncSession,
    user_id: uuid.UUID,
    job_description_id: uuid.UUID | str | None = None,
) -> dict:
    """Run the full deterministic analysis pipeline and persist the result."""

    # ── 1. Fetch latest resume ───────────────────────────────────────────────
    resume_result = await db.execute(
        select(Resume)
        .where(Resume.user_id == user_id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    resume = resume_result.scalar_one_or_none()
    if not resume:
        raise ValueError("No resume found for user.")

    raw_text = resume.raw_text or ""

    # ── 2. Fetch experiences & projects tied to this resume ─────────────────
    exp_result = await db.execute(
        select(Experience).where(
            Experience.user_id == user_id,
            Experience.resume_id == resume.id,
        )
    )
    experiences = list(exp_result.scalars().all())

    proj_result = await db.execute(
        select(Project).where(
            Project.user_id == user_id,
            Project.resume_id == resume.id,
        )
    )
    projects = list(proj_result.scalars().all())

    edu_result = await db.execute(
        select(Education).where(
            Education.user_id == user_id,
            Education.resume_id == resume.id,
        )
    )
    education = list(edu_result.scalars().all())

    all_bullets = _collect_bullets(experiences, projects)

    # ── 3. JD keyword extraction (if provided) ───────────────────────────────
    jd_keywords: set[str] | None = None
    if job_description_id:
        jd_id = uuid.UUID(str(job_description_id))
        jd_result = await db.execute(
            select(JobDescription).where(
                JobDescription.id == jd_id,
                JobDescription.user_id == user_id,
            )
        )
        jd = jd_result.scalar_one_or_none()
        if jd and jd.extracted_requirements:
            skills = jd.extracted_requirements.get("skills", [])
            if skills:
                jd_keywords = {s.lower() for s in skills if s}

    # ── 4. Run all modules ───────────────────────────────────────────────────
    structure  = analyze_structure(raw_text)
    parsing    = analyze_parsing(raw_text)
    formatting = analyze_formatting(raw_text)
    content    = analyze_content(all_bullets)
    metrics    = analyze_metrics(all_bullets)

    # Fetch user's profile skills to use as keyword pool if no target JD is chosen
    profile_skills = set()
    if not jd_keywords:
        # GitHub
        gh_rows = await db.execute(
            select(GithubSnapshot.languages).where(GithubSnapshot.user_id == user_id)
        )
        for row in gh_rows.fetchall():
            if row[0]:
                profile_skills.update(k.lower() for k in row[0].keys())

        # Leetcode
        lc_ev_rows = await db.execute(
            select(Skill.canonical_name)
            .join(LeetcodeSnapshot, (LeetcodeSnapshot.tag == Skill.name) | (LeetcodeSnapshot.tag == Skill.canonical_name))
            .where(LeetcodeSnapshot.user_id == user_id)
        )
        profile_skills.update(r[0].lower() for r in lc_ev_rows.fetchall() if r[0])

        # Certificates
        cert_ev_rows = await db.execute(
            select(Certificate.skills).where(Certificate.user_id == user_id)
        )
        for row in cert_ev_rows.fetchall():
            if row[0]:
                profile_skills.update(s.lower() for s in row[0])

        # Experience & Project stacks
        for exp in experiences:
            if exp.stack:
                profile_skills.update(s.lower() for s in exp.stack)
        for proj in projects:
            if proj.stack:
                profile_skills.update(s.lower() for s in proj.stack)

        # Filter out generic/algorithmic Leetcode topics that shouldn't be recommended as resume keywords
        profile_skills = {s for s in profile_skills if s not in EXCLUDED_SKILLS}

    keywords   = analyze_keywords(raw_text, jd_keywords, profile_skills if profile_skills else None)
    evidence   = await analyze_evidence(db, user_id, resume.id)

    # ── 5. Run ATS v2 Scorer ────────────────────────────────────────────────
    from app.services.resume.analysis.ats_scorer_v2 import analyze_ats_v2
    ats_res = analyze_ats_v2(
        raw_text=raw_text,
        experiences=experiences,
        projects=projects,
        education=education,
        profile_skills=profile_skills if profile_skills else None
    )

    overall = ats_res["score"]
    module_scores = ats_res["module_scores"]
    grade = get_grade(overall)
    label = get_label(overall)
    grade_color = get_grade_color(overall)

    # ── 6. Role Compatibility (deterministic — never LLM-invented) ──────────
    from app.services.resume.analysis.role_fit import compute_role_fit
    role_fit = compute_role_fit(evidence.get("skills", []))

    # ── 7. Suggestions ───────────────────────────────────────────────────────
    # FIX (Critical #1): ats_res["warnings"] is the SAME warnings list that
    # produced `overall`/`grade`/`label` above — passing it in guarantees the
    # displayed score and the displayed reasons for that score can never
    # disagree.
    suggestions = generate_suggestions(
        structure, parsing, formatting, content, metrics, keywords, evidence,
        ats_warnings=ats_res.get("warnings", []),
    )

    report: dict = {
        "overall_score":  overall,
        "grade":          grade,
        "label":          label,
        "grade_color":    grade_color,
        "module_scores":  module_scores,
        "warnings":       ats_res.get("warnings", []),
        "role_fit":       role_fit,
        "modules": {
            "structure":  structure,
            "parsing":    parsing,
            "formatting": formatting,
            "content":    content,
            "metrics":    metrics,
            "keywords":   keywords,
            "evidence":   evidence,
        },
        "suggestions": suggestions,
        "resume_id":   str(resume.id),
        "created_at":  datetime.now(timezone.utc).isoformat(),
    }

    # ── 7. Persist ───────────────────────────────────────────────────────────
    row = ResumeAnalysis(
        user_id=user_id,
        resume_id=resume.id,
        analysis_json=report,
    )
    db.add(row)
    await db.flush()
    await db.commit()

    return report
