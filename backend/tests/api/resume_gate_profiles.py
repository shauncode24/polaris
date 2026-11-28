"""Ten made-up people, each with a job, for the truthfulness gate. Several set a
trap: a way for the resume to say something their record doesn't.
"""
from dataclasses import dataclass, field

from app.models.facts import Education, Experience, Project, UserSkillOverride
from app.models.linkedin import LinkedInProfile
from tests.api.test_evidence import run
from tests.api.test_resume_selection import NOW, add, evidence, experience, new_user, project, repo, upload
from tests.api.test_skill_gap_evidence import _skill


@dataclass
class Role:
    role: str
    company: str
    stack: list[str]
    bullets: list[str]
    skills: list[str] = field(default_factory=list)  # canonical names the record counts it as evidence of
    fields: dict = field(default_factory=dict)


@dataclass
class Work:
    name: str
    stack: list[str] = field(default_factory=list)
    description: str | None = None
    skills: list[str] = field(default_factory=list)
    repo: list[str] | None = None  # technologies found in its repository
    repo_skills: list[str] = field(default_factory=list)
    fields: dict = field(default_factory=dict)


@dataclass
class Profile:
    key: str
    job: list[tuple[str, str]]  # (the job's wording, canonical name)
    nice: list[tuple[str, str]] = field(default_factory=list)
    roles: list[Role] = field(default_factory=list)
    projects: list[Work] = field(default_factory=list)
    school: list[str] | None = None  # the details of one education entry
    linkedin: list[str] = field(default_factory=list)  # skills listed there
    linkedin_skills: list[str] = field(default_factory=list)
    leetcode: list[str] = field(default_factory=list)  # canonical skills practised
    hidden_skills: list[str] = field(default_factory=list)


PROFILES = [
    Profile(
        "backend engineer",
        job=[("PostgreSQL", "postgres"), ("Python", "python"), ("REST APIs", "rest_api"),
             ("Kubernetes", "kubernetes")],
        roles=[Role("Backend Engineer", "Initech", ["Python", "Postgres"], [
            "Tuned Postgres queries for the billing service, cutting report time from 40s to 6s.",
            "Helped design a small REST API in Python for the mobile team.",
            "Wrote the on-call handbook.",
        ], skills=["python", "postgres"], fields={"start_date_text": "Jun 2023", "end_date_text": "Present"})],
        projects=[Work("Ledger", ["Python"], "Double-entry ledger in Python.\nDeployed it for a student club.",
                       skills=["python"])],
        school=["Coursework in databases."],
    ),
    Profile(
        # "version control" counts as Git, and "unit testing" as testing, but neither says so.
        "skills known only by another name",
        job=[("Git", "git"), ("Testing", "testing"), ("Python", "python")],
        roles=[Role("Teaching Assistant", "State University", ["version control", "unit testing", "Python"], [
            "Set up version control for the lab's Python scripts.",
            "Wrote unit testing exercises for 30 students.",
        ], skills=["git", "testing", "python"])],
    ),
    Profile(
        "frontend",
        job=[("React.js", "react"), ("TypeScript", "typescript"), ("GraphQL", "graphql")],
        roles=[Role("Frontend Developer", "Globex", ["React", "TypeScript"], [
            "Built React screens for the checkout flow.",
            "Migrated one page to TypeScript with a senior developer.",
        ], skills=["react", "typescript"])],
        projects=[Work("Portfolio", ["React", "CSS"], "A React portfolio site.", skills=["react", "css"])],
    ),
    Profile(
        "evidence only from GitHub",
        job=[("Terraform", "terraform"), ("Docker", "docker"), ("Kubernetes", "kubernetes"),
             ("Amazon Web Services", "aws")],
        projects=[Work("infra", [], "Provisions two test servers with Terraform.", fields={"source": "github"},
                       repo=["Terraform", "Docker"], repo_skills=["terraform", "docker"])],
    ),
    Profile(
        "student with practice",
        job=[("Java", "java"), ("Algorithms", "algorithms"), ("Data Structures", "data_structures")],
        projects=[Work("Maze", ["Java"], "Solves mazes in Java with breadth-first search.", skills=["java"])],
        school=["Dean's list, 2025."],
        leetcode=["algorithms", "data_structures", "dynamic_programming"],
    ),
    Profile(
        "LinkedIn only",
        job=[("Machine Learning", "machine_learning"), ("Python", "python"), ("Spark", "spark")],
        roles=[Role("Research Intern", "Umbrella", [], [
            "Assisted with an ML prototype in Python.",
        ], fields={"source": "linkedin"})],
        linkedin=["ML", "Python"],
        linkedin_skills=["machine_learning", "python"],
    ),
    Profile(
        # The user has since taken Docker and Redis off these items, and hidden a skill.
        "record edited since it was imported",
        job=[("Docker", "docker"), ("Redis", "redis"), ("Python", "python"), ("Kafka", "kafka")],
        roles=[Role("Engineer", "Hooli", ["Python"], ["Maintained Python services."],
                    skills=["python", "docker", "kafka"])],
        projects=[Work("Cache", ["Python"], "A cache written in Python.", skills=["python", "redis"])],
        hidden_skills=["kafka"],
    ),
    Profile(
        "data analyst",
        job=[("SQL", "sql"), ("Spark", "spark"), ("Airflow", "airflow")],
        roles=[Role("Analyst", "Wonka", ["SQL", "Excel"], [
            "Queried the cloud data warehouse with SQL to prepare weekly sales figures for 3 managers.",
        ], skills=["sql"])],
    ),
    Profile(
        "junior whose work is hedged",
        job=[("Node.js", "nodejs"), ("MongoDB", "mongodb")],
        roles=[Role("Intern", "Stark", ["Node", "Mongo"], [
            "Helped the team move some Node services to a new host.",
            "Attended training and built a demo app on Mongo.",
            "Contributed to 2 internal Node tools.",
        ], skills=["nodejs", "mongodb"])],
    ),
    Profile(
        "almost nothing",
        job=[("Go", "go"), ("Kubernetes", "kubernetes")],
        projects=[Work("Untitled", [], None)],
        school=[],
    ),
]


def create(profile: Profile):
    """The profile as the app stores it, with skill evidence like ingestion's."""
    user = new_user(first_name="Casey", last_name="Okafor", github_username="casey")
    latest = upload(user)
    for item in profile.roles:
        fields = {"resume_id": latest, **item.fields} if item.fields.get("source") != "linkedin" else item.fields
        row = experience(user, item.role, item.stack, item.bullets, company=item.company, **fields)
        for skill in item.skills:
            evidence(user, skill, "experience", row)
    for item in profile.projects:
        fields = dict(item.fields)
        if item.repo is not None:
            analysis = repo(user, item.name, item.repo)
            fields["github_repo_name"] = item.name
            for skill in item.repo_skills:
                evidence(user, skill, "github_repo", analysis)
        row = project(user, item.name, item.stack, item.description, **fields)
        for skill in item.skills:
            evidence(user, skill, "project", row)
    if profile.school is not None:
        add(Education(user_id=user.id, resume_id=latest, institution="State University", degree="BSc",
                      field_of_study="Computer Science", start_date_text="2021", end_date_text="2025",
                      details=profile.school, created_at=NOW))
    if profile.linkedin:
        row = add(LinkedInProfile(user_id=user.id, raw_text="r", parsed_json={"skills": profile.linkedin},
                                  created_at=NOW))
        for skill in profile.linkedin_skills:
            evidence(user, skill, "linkedin_profile", row)
    for skill in profile.leetcode:
        evidence(user, skill, "leetcode_tag", None)
    # Things the user has hidden, which must not come back.
    experience(user, "Secret Role", ["Rust"], ["Rewrote everything in Rust."], company="Hidden Co", is_hidden=True)
    project(user, "Secret Project", ["Elixir"], "Hidden work in Elixir.", is_hidden=True)

    async def hide(db):
        for canonical in profile.hidden_skills:
            skill = await _skill(db, canonical)
            db.add(UserSkillOverride(user_id=user.id, skill_id=skill.id, is_hidden=True, updated_at=NOW))
        await db.commit()
    run(hide)
    return user
