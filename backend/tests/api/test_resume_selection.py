"""What is chosen for the resume tailored to a job. Real database; no model."""
import uuid
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import select

from app.models.facts import Education, Experience, Project, Resume, User, UserSkillOverride
from app.models.github_analysis import GithubProjectAnalysis
from app.models.inference import ProjectClaimAuditReview, SkillEvidence
from app.services.resume.selection import select_for_job
from tests.api.test_evidence import run
from tests.api.test_job_library import add_job
from tests.api.test_skill_gap_evidence import _skill
from tests.llm_stub import model  # noqa: F401 (model is a fixture)

NOW = datetime.now(timezone.utc)


def new_user(**fields):
    async def go(db):
        user = User(**{"name": "Sam Rivera", "email": f"{uuid.uuid4().hex}@example.test", "auth_provider": "local",
                       "target_roles": [], "target_companies": [], **fields})
        db.add(user)
        await db.commit()
        return SimpleNamespace(id=user.id, email=user.email)
    return run(go)


def add(row):
    async def go(db):
        db.add(row)
        await db.commit()
        return row.id
    return run(go)


def upload(user, *, days_ago=0):
    return add(Resume(user_id=user.id, raw_text="r", created_at=NOW - timedelta(days=days_ago)))


_made = [0]


def _next_time(days_ago=0):
    """Rows are created in the order the tests add them."""
    _made[0] += 1
    return NOW - timedelta(days=days_ago) + timedelta(milliseconds=_made[0])


def project(user, name, stack=(), description=None, *, days_ago=0, **fields):
    return add(Project(user_id=user.id, name=name, stack=list(stack), description=description,
                       created_at=_next_time(days_ago), **fields))


def experience(user, role, stack=(), bullets=(), *, company="Acme", days_ago=0, **fields):
    return add(Experience(user_id=user.id, role=role, company=company, stack=list(stack), bullets=list(bullets),
                          created_at=_next_time(days_ago), **fields))


def evidence(user, canonical, kind, source_id, weight=0.35):
    async def go(db):
        skill = await _skill(db, canonical)
        db.add(SkillEvidence(user_id=user.id, skill_id=skill.id, source_type=kind, source_id=source_id,
                             weight=weight, created_at=NOW))
        await db.commit()
    run(go)


def repo(user, name, technologies):
    return add(GithubProjectAnalysis(
        user_id=user.id, repo_name=name, category="Backend", technologies=list(technologies), capabilities=[],
        html_url=f"https://github.com/sam/{name}", computed_at=NOW,
    ))


def select_(user, job_id):
    async def go(db):
        return await select_for_job(db, user.id, uuid.UUID(job_id))
    return run(go)


def names(entries) -> list[str]:
    return [getattr(e, "name", None) or e.role for e in entries]


def skill_names(document) -> list[str]:
    return [s.canonical for s in document.skills]


def test_projects_are_ranked_by_what_the_job_asks_for(seeded):
    user = new_user(first_name="Sam", last_name="Rivera", github_username="sam", location_pref="Remote")
    project(user, "Nice to have", ["Docker"])
    project(user, "Unrelated", ["Photoshop"])
    project(user, "Required", ["FastAPI", "PostgreSQL"], "A ledger API.")
    job = add_job(user, "Backend Engineer", ["fastapi", "postgres"], nice=["docker"])

    result = select_(user, job)

    assert names(result.document.projects) == ["Required", "Nice to have"]
    assert [(r.label, r.selected) for r in result.ranking] == [
        ("Required", True), ("Nice to have", True), ("Unrelated", False),
    ]
    assert result.ranking[0].matched_skills == ["fastapi", "postgres"]
    entry = result.document.projects[0]
    assert (entry.bullets[0].original, entry.bullets[0].decision, entry.bullets[0].rewrite) == (
        "A ledger API.", "pending", None)
    header = result.document.header
    assert (header.full_name, header.email, header.location) == ("Sam Rivera", user.email, None)
    assert [link.url for link in header.links] == ["https://github.com/sam"]


def test_only_so_many_are_chosen_and_unrelated_projects_only_fill_gaps(seeded):
    many = new_user()
    for number in range(6):
        project(many, f"P{number}", ["Python"])
    assert len(select_(many, add_job(many, "Engineer", ["python"])).document.projects) == 4

    few = new_user()
    project(few, "Relevant", ["Python"])
    project(few, "Bare", ["Photoshop"], days_ago=0)
    project(few, "Described", ["Photoshop"], "Edits photos.", days_ago=3)
    project(few, "Another", ["Photoshop"], "Draws.", days_ago=5)
    assert names(select_(few, add_job(few, "Engineer", ["python"])).document.projects) == ["Relevant", "Described"]


def test_the_most_relevant_roles_are_chosen_and_shown_in_resume_order(seeded):
    user = new_user()
    resume = upload(user)
    for number, stack in enumerate([[], ["Python"], [], ["Python"], ["Python"], ["Python"]]):
        experience(user, f"Role {number}", stack, company=f"C{number}", resume_id=resume)
    job = add_job(user, "Engineer", ["python"])

    assert names(select_(user, job).document.experience) == ["Role 1", "Role 3", "Role 4", "Role 5"]


def test_dated_roles_go_newest_first(seeded):
    user = new_user()
    resume = upload(user)
    experience(user, "Old", resume_id=resume, company="A", start_date=date(2020, 1, 1), end_date=date(2021, 1, 1))
    experience(user, "Current", resume_id=resume, company="B", start_date=date(2024, 1, 1))
    experience(user, "Recent", resume_id=resume, company="C", start_date=date(2022, 1, 1), end_date=date(2023, 1, 1))
    job = add_job(user, "Engineer", ["python"])

    assert names(select_(user, job).document.experience) == ["Current", "Recent", "Old"]


def test_the_latest_upload_and_linkedin_are_both_used(seeded):
    user = new_user()
    old, new = upload(user, days_ago=30), upload(user)
    experience(user, "Engineer", bullets=["Old wording."], resume_id=old, days_ago=30)
    experience(user, "Intern", company="Past Co", resume_id=old, days_ago=30)
    experience(user, "Volunteer", company="Club", source="linkedin")
    latest = experience(user, "Engineer", bullets=["New wording."], resume_id=new)
    add(Education(user_id=user.id, resume_id=new, institution="State University", degree="BSc",
                  details=["GPA 8.4"], created_at=NOW))
    job = add_job(user, "Engineer", ["python"])

    document = select_(user, job).document

    assert names(document.experience) == ["Engineer", "Intern", "Volunteer"]
    assert [line.text for line in document.experience[0].bullets] == ["New wording."]
    assert document.experience[0].sources[0].id == latest
    assert [(e.institution, e.bullets[0].text) for e in document.education] == [("State University", "GPA 8.4")]


def test_hidden_items_never_appear_nor_bring_back_older_copies(seeded):
    user = new_user()
    project(user, "Secret", ["Python"], "Old copy.", days_ago=10)
    project(user, "Secret", ["Python"], "New copy.", is_hidden=True)
    experience(user, "Spy", ["Python"], is_hidden=True)
    add(Education(user_id=user.id, institution="Hidden College", is_hidden=True, created_at=NOW))
    job = add_job(user, "Engineer", ["python"])

    result = select_(user, job)

    document = result.document
    assert (document.projects, document.experience, document.education, result.ranking) == ([], [], [], [])


def test_a_hidden_skill_is_neither_listed_nor_counted(seeded):
    user = new_user()
    item = project(user, "Tool", ["Python", "Docker"])
    evidence(user, "python", "project", item)
    evidence(user, "docker", "project", item)

    async def hide(db):
        skill = await _skill(db, "docker")
        db.add(UserSkillOverride(user_id=user.id, skill_id=skill.id, is_hidden=True, updated_at=NOW))
        await db.commit()
    run(hide)
    job = add_job(user, "Engineer", ["python", "docker"])

    result = select_(user, job)

    assert skill_names(result.document) == ["python"]
    assert result.document.projects[0].technologies == ["Python"]
    assert result.ranking[0].matched_skills == ["python"]


def test_only_skills_with_evidence_are_listed_in_the_jobs_order_of_need(seeded):
    user = new_user()
    item = project(user, "Tool", ["PostgreSQL", "python"])
    evidence(user, "redis", "project", item, weight=0.9)  # not asked for
    evidence(user, "docker", "project", item)
    evidence(user, "python", "project", item)
    evidence(user, "dynamic_programming", "leetcode_tag", None)  # practice only, not asked for
    evidence(user, "algorithms", "leetcode_tag", None)  # practice only, asked for
    job = add_job(user, "Engineer", ["python", "algorithms", "kubernetes"], nice=["docker"])

    document = select_(user, job).document

    found = skill_names(document)
    assert found[:2] == sorted(["python", "algorithms"], key=found.index)  # required first
    assert set(found[:2]) == {"python", "algorithms"}
    assert found[2:] == ["docker", "redis"]  # then nice to have, then the rest
    assert "kubernetes" not in found and "dynamic_programming" not in found
    by_name = {s.canonical: s for s in document.skills}
    assert by_name["python"].name == "python"  # as the user wrote it
    assert [(r.kind, r.id) for r in by_name["algorithms"].sources] == [("leetcode_tag", None)]
    assert [(r.kind, r.id) for r in by_name["python"].sources] == [("project", item)]


def test_a_github_projects_code_counts_and_is_cited(seeded):
    user = new_user()
    analysis = repo(user, "infra", ["Terraform"])
    item = project(user, "infra", [], "Provisions servers.", source="github", github_repo_name="infra")
    evidence(user, "terraform", "github_repo", analysis, weight=0.3)
    job = add_job(user, "Platform Engineer", ["terraform"])

    result = select_(user, job)

    entry = result.document.projects[0]
    assert result.ranking[0].matched_skills == ["terraform"]
    assert entry.technologies == ["Terraform"]
    assert entry.url == "https://github.com/sam/infra"
    assert [(s.kind, s.id) for s in entry.sources] == [("project", item), ("github_repo", analysis)]


def test_an_unsupported_claim_lowers_a_projects_rank(seeded):
    user = new_user()
    doubtful = project(user, "Doubtful", ["Python", "Docker"])
    project(user, "Sound", ["Python"])
    job = add_job(user, "Engineer", ["python", "docker"])
    assert names(select_(user, job).document.projects) == ["Doubtful", "Sound"]

    add(ProjectClaimAuditReview(user_id=user.id, project_id=doubtful,
                                report_json={"narrative": {"risk_level": "high"}, "facts": {}}))
    result = select_(user, job)

    # Halved from 2.0 it ties with the sound project; a medium risk would not be enough to.
    scores = {r.label: (r.relevance_score, r.claim_risk) for r in result.ranking}
    assert scores == {"Doubtful": (1.0, "high"), "Sound": (1.0, None)}


def test_bullets_that_show_what_the_job_needs_come_first(seeded):
    user = new_user()
    bullets = ["Wrote documentation.", "  ", "Used Docker.", "Built Python services on PostgreSQL.",
               "Attended meetings.", "Reviewed Python code.", "Ordered lunch.", "Fixed printers."]
    item = experience(user, "Engineer", bullets=bullets)
    project(user, "Tool", ["Python"], "- Parses logs.\n\n2) Written in Python.\n• Has tests.\nDeployed weekly.")
    job = add_job(user, "Engineer", ["python", "postgres"], nice=["docker"])

    document = select_(user, job).document

    chosen = document.experience[0].bullets
    assert [line.text for line in chosen] == [
        "Built Python services on PostgreSQL.", "Reviewed Python code.", "Used Docker.",
        "Wrote documentation.", "Attended meetings.",
    ]
    assert [(line.sources[0].id, line.sources[0].bullet) for line in chosen[:2]] == [(item, 3), (item, 5)]
    assert [line.text for line in document.projects[0].bullets] == [
        "Written in Python.", "Parses logs.", "Has tests.",
    ]


def test_nothing_is_asked_of_the_model(seeded, model):
    user = new_user()
    item = project(user, "Tool", [f"Unheard{uuid.uuid4().hex[:8]}"])
    experience(user, "Engineer", [f"Unheard{uuid.uuid4().hex[:8]}"])
    evidence(user, "python", "experience", item)
    job = add_job(user, "Engineer", ["python"])

    assert select_(user, job) is not None
    assert model.requests == []


def test_evidence_that_cannot_be_pointed_at_is_left_out(seeded):
    user = new_user()
    evidence(user, "python", "hearsay", uuid.uuid4())
    evidence(user, "docker", "project", None)

    assert select_(user, add_job(user, "Engineer", ["python", "docker"])).document.skills == []


def test_every_source_is_the_users_own(seeded):
    user, other = new_user(), new_user()
    for owner in (user, other):
        item = project(owner, "Shared name", ["Python"], "Does things.")
        role = experience(owner, "Engineer", ["Python"], ["Did things."])
        evidence(owner, "python", "project", item)
        evidence(owner, "python", "experience", role)
    job = add_job(user, "Engineer", ["python"])

    document = select_(user, job).document

    async def owned(db):
        found = set()
        for model_ in (Project, Experience):
            found |= set((await db.execute(select(model_.id).where(model_.user_id == user.id))).scalars().all())
        return found
    entries = [*document.projects, *document.experience, *document.skills]
    cited = {s.id for e in entries for s in e.sources} | {s.id for line in document.lines() for s in line.sources}
    assert cited and cited <= run(owned)


def test_another_users_job_gives_nothing_and_an_empty_record_gives_a_header(seeded):
    user, other = new_user(), new_user()
    job = add_job(user, "Engineer", ["python"])

    assert select_(other, job) is None
    document = select_(user, job).document
    assert (document.projects, document.experience, document.skills, document.summary) == ([], [], [], None)
    assert document.header.full_name == "Sam Rivera"
