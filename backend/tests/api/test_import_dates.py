"""Dates stated in a resume or a LinkedIn profile are saved and used. Real
database and imports; only the model is stubbed.
"""
import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select

from app.models.facts import Education, Experience, Project, User
from app.models.github_analysis import GithubProjectAnalysis
from app.services.linkedin.linkedin_ingestion import ingest_linkedin_profile
from app.services.resume.ingestion import ingest_resume
from app.services.resume.selection import select_for_job
from app.services.resume.timeline_plausibility import build_timeline_plausibility_notes
from tests.api.test_evidence import auth, run
from tests.api.test_job_library import add_job
from tests.api.test_resume_selection import new_user
from tests.llm_stub import model  # noqa: F401 (model is a fixture)

RESUME = {
    "experiences": [
        {"role": "Intern", "company": "Acme", "start_date": "Jun 2024", "end_date": "Aug 2024",
         "stack": ["Python"], "bullets": ["Built an API in Python."]},
        {"role": "Engineer", "company": "Globex", "start_date": "2025", "end_date": "Present",
         "stack": [], "bullets": []},
    ],
    "projects": [],
    "education": [{"institution": "State University", "degree": "BSc", "end_date": "Expected 2027",
                   "is_current": True, "details": []},
                  # A lone graduation year, returned in the wrong field.
                  {"institution": "City School", "start_date": "2023", "is_current": False, "details": []}],
    "skills": [],
}
LINKEDIN = {
    "experience": [{"role": "Volunteer", "company": "Club", "date_range": "Jan 2022 - Mar 2023 · 1 yr", "bullets": []}],
    "education": [{"institution": "City College", "date_range": "2019 - 2023"}],
    "skills": [], "headline": None, "about": None, "achievements": [],
}


def upload(user, model, reply):
    model.will(reply)

    async def go(db):
        return await ingest_resume("resume text", db, await db.get(User, user.id))
    return run(go)


def paste(user, model, reply):
    model.will(reply)

    async def go(db):
        result = await ingest_linkedin_profile(db, await db.get(User, user.id), "profile text")
        await db.commit()
        return result
    return run(go)


def rows(user, table, name) -> dict:
    async def go(db):
        result = await db.execute(select(table).where(table.user_id == user.id))
        return {
            getattr(r, name): (r.start_date, r.end_date, r.start_date_text, r.end_date_text)
            for r in result.scalars().all()
        }
    return run(go)


def test_a_resume_upload_saves_its_dates(seeded, model):
    user = new_user()

    upload(user, model, RESUME)

    assert rows(user, Experience, "role") == {
        "Intern": (date(2024, 6, 1), date(2024, 8, 1), "Jun 2024", "Aug 2024"),
        "Engineer": (date(2025, 1, 1), None, "2025", "Present"),
    }
    assert rows(user, Education, "institution") == {
        "State University": (None, date(2027, 1, 1), None, "Expected 2027"),
        "City School": (None, date(2023, 1, 1), None, "2023"),
    }


def test_a_tailored_resume_shows_the_dates_as_written_newest_first(client, seeded, model):
    user = new_user()
    upload(user, model, RESUME)
    job = add_job(user, "Engineer", ["python"])

    async def go(db):
        return await select_for_job(db, user.id, uuid.UUID(job))
    document = run(go).document

    assert [(e.role, e.start_date_text, e.end_date_text) for e in document.experience] == [
        ("Engineer", "2025", "Present"), ("Intern", "Jun 2024", "Aug 2024"),
    ]
    assert document.education[0].end_date_text == "Expected 2027"
    shown = client.get("/profile/data", headers=auth(user.id)).json()["experiences"]
    assert {e["title"]: (e["start_year"], e["end_year"]) for e in shown} == {
        "Engineer": (2025, None), "Intern": (2024, 2024),
    }


def test_a_role_with_only_present_counts_as_the_newest(seeded, model):
    user = new_user()
    upload(user, model, {**RESUME, "experiences": [
        {"role": "Old", "company": "A", "start_date": "2020", "end_date": "2021", "stack": [], "bullets": []},
        {"role": "Now", "company": "B", "end_date": "Present", "stack": [], "bullets": []},
    ]})
    job = add_job(user, "Engineer", ["python"])

    async def go(db):
        return await select_for_job(db, user.id, uuid.UUID(job))

    assert [e.role for e in run(go).document.experience] == ["Now", "Old"]


def test_a_linkedin_import_saves_its_dates(seeded, model):
    user = new_user()

    paste(user, model, LINKEDIN)

    assert rows(user, Experience, "role") == {
        "Volunteer": (date(2022, 1, 1), date(2023, 3, 1), "Jan 2022", "Mar 2023"),
    }
    assert rows(user, Education, "institution") == {
        "City College": (date(2019, 1, 1), date(2023, 1, 1), "2019", "2023"),
    }


def test_pasting_linkedin_again_fills_in_missing_dates_only(seeded, model):
    user = new_user()

    async def earlier_imports(db):
        now = datetime.now(timezone.utc)
        db.add(Experience(user_id=user.id, role="Volunteer", company="Club", source="linkedin", created_at=now))
        db.add(Education(user_id=user.id, institution="City College", source="resume", created_at=now))
        await db.commit()
    run(earlier_imports)

    paste(user, model, LINKEDIN)

    assert rows(user, Experience, "role")["Volunteer"][2:] == ("Jan 2022", "Mar 2023")
    # A row from the resume is the resume's to date.
    assert rows(user, Education, "institution")["City College"] == (None, None, None, None)

    other = {**LINKEDIN, "experience": [{**LINKEDIN["experience"][0], "date_range": "2001 - 2002"}]}
    paste(user, model, other)
    assert rows(user, Experience, "role")["Volunteer"][2:] == ("Jan 2022", "Mar 2023")


@pytest.mark.parametrize("ended, repo_created, noted", [
    # "2023" may mean December: a repo from the following spring is close enough.
    ("2023", date(2024, 4, 1), False),
    ("2023", date(2025, 1, 1), True),
    ("Jan 2023", date(2024, 4, 1), True),
    ("Present", date(2025, 1, 1), False),
])
def test_the_timeline_check_allows_for_how_precise_the_date_is(seeded, model, ended, repo_created, noted):
    user = new_user()
    upload(user, model, {**RESUME, "experiences": [
        {"role": "Intern", "company": "Acme", "start_date": "2022", "end_date": ended,
         "stack": ["Python"], "bullets": []},
    ]})

    async def check(db):
        db.add(GithubProjectAnalysis(
            user_id=user.id, repo_name="r", category="Backend", technologies=["python"], capabilities=[],
            computed_at=datetime.now(timezone.utc),
            repo_created_at=datetime.combine(repo_created, datetime.min.time(), timezone.utc),
        ))
        await db.commit()
        resume_id = await db.scalar(select(Experience.resume_id).where(Experience.user_id == user.id))
        return await build_timeline_plausibility_notes(db, user.id, resume_id)

    assert bool(run(check)) is noted
