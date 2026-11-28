"""Whether what a tailored resume cites is in the user's record. Real database."""
import uuid

from app.models.facts import Education, Experience, Project
from app.models.linkedin import LinkedInProfile
from app.schemas.resume.tailored import SkillEntry, SourceRef
from app.services.resume.grounding import unsupported_sources
from tests.api.test_evidence import run
from tests.api.test_job_library import add_job
from tests.api.test_resume_selection import NOW, add, evidence, experience, new_user, project, repo, select_


def problems(user, document) -> list[str]:
    async def go(db):
        return await unsupported_sources(db, user.id, document)
    return run(go)


def change(model_, row_id, **fields):
    async def go(db):
        row = await db.get(model_, row_id)
        for name, value in fields.items():
            setattr(row, name, value)
        await db.commit()
    run(go)


def record():
    """A user with one of each kind of source, and the resume chosen from it."""
    user = new_user()
    role = experience(user, "Engineer", ["Python"], ["Wrote Python.", "  ", "Used Docker."])
    tool = project(user, "Tool", ["Terraform"], "- Parses logs.\n\n2) Written in Python.",
                   source="github", github_repo_name="Tool")
    analysis = repo(user, "Tool", ["Terraform"])
    school = add(Education(user_id=user.id, institution="State University", details=["GPA 8.4"], created_at=NOW))
    profile = add(LinkedInProfile(user_id=user.id, raw_text="r", parsed_json={}, created_at=NOW))
    evidence(user, "python", "experience", role)
    evidence(user, "terraform", "github_repo", analysis)
    evidence(user, "docker", "linkedin_profile", profile)
    evidence(user, "algorithms", "leetcode_tag", None)
    document = select_(user, add_job(user, "Engineer", ["python", "terraform", "docker", "algorithms"])).document
    return user, document, {"role": role, "project": tool, "school": school}


def test_a_chosen_resume_cites_only_what_is_there(seeded):
    user, document, _ids = record()

    kinds = {ref.kind for item in [*document.skills, *document.projects, *document.education] for ref in item.sources}
    assert kinds == {"experience", "project", "github_repo", "education", "linkedin_profile", "leetcode_tag"}
    assert len(document.lines()) == 5
    assert problems(user, document) == []


def test_another_users_record_supports_nothing(seeded):
    _user, document, ids = record()

    found = problems(new_user(), document)

    assert any(str(ids["role"]) in problem for problem in found)
    assert sum("does not quote" in problem for problem in found) == len(document.lines())


def test_a_row_that_is_not_there_is_reported(seeded):
    user, document, _ids = record()
    missing = uuid.uuid4()
    document.skills.append(SkillEntry(name="Go", canonical="go", sources=[SourceRef(kind="certificate", id=missing)]))
    document.skills.append(
        SkillEntry(name="C", canonical="c", sources=[SourceRef(kind="leetcode_tag", id=missing)])
    )

    assert problems(user, document) == [
        f"certificate {missing} is not in the record", f"leetcode_tag {missing} is not in the record",
    ]


def test_original_wording_must_be_the_cited_bullets(seeded):
    user, document, _ids = record()
    first, second = document.experience[0].bullets
    first.original = "Led a team of 20."
    second.sources[0].bullet = 9
    uncited = document.projects[0].bullets[0]
    uncited.sources[0].bullet = None

    assert problems(user, document) == [
        f"line {line.id} does not quote a bullet it cites" for line in (first, second, uncited)
    ]


def test_a_bullet_changed_or_hidden_since_is_no_longer_supported(seeded):
    user, document, ids = record()

    change(Experience, ids["role"], bullets=["Reworded."])
    assert sum("does not quote" in problem for problem in problems(user, document)) == 2

    change(Project, ids["project"], is_hidden=True)
    assert f"project {ids['project']} is not in the record" in problems(user, document)
