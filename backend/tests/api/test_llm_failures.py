"""What reaches the user, and what is remembered, when the model fails. Real
database; only the model is stubbed.
"""
from openai import RateLimitError
from sqlalchemy import select

from app.models.structure import CompetencyTagAlias, SkillAlias
from app.services.interview.competency_tagging import tag_or_backfill_items
from app.services.resume.skill_classifier import resolve_skills
from tests.api.test_evidence import run
from tests.llm_stub import api_error, model  # noqa: F401 (model is a fixture)


# Text extraction is stubbed, so the upload only has to look like a PDF.
PDF = b"%PDF-1.4 stub"


def test_a_resume_upload_that_hits_the_limit_says_so(client, bob_headers, model, monkeypatch):
    async def text(raw_bytes):
        return "Engineer at Acme"
    monkeypatch.setattr("app.api.resume.extract_text_from_pdf_bytes", text)
    model.will(api_error(RateLimitError, 429))

    response = client.post(
        "/resume/upload", files={"file": ("cv.pdf", PDF, "application/pdf")}, headers=bob_headers,
    )

    assert response.status_code == 503, response.text[:300]
    assert response.json() == {"detail": "The AI service has reached its usage limit. Try again in a few minutes."}


def test_a_cut_off_resume_is_refused_instead_of_saved(client, bob_headers, model, monkeypatch):
    async def text(raw_bytes):
        return "Engineer at Acme"
    monkeypatch.setattr("app.api.resume.extract_text_from_pdf_bytes", text)
    cut_off = {"experiences": [{"role": "Engineer", "company": "Acme"}]}
    model.will(cut_off, cut_off)

    response = client.post(
        "/resume/upload", files={"file": ("cv.pdf", PDF, "application/pdf")}, headers=bob_headers,
    )

    assert response.status_code == 502, response.text[:300]
    assert "incomplete" in response.json()["detail"]


def test_a_skill_the_model_skips_is_not_remembered_as_not_a_skill(seeded, model):
    model.will({"results": [{"raw": "Zigzag Lang", "canonical": "zigzag", "is_valid_skill": True}]})

    async def go(db):
        resolved = await resolve_skills({"Zigzag Lang", "Quux Engine"}, db)
        cached = (await db.execute(
            select(SkillAlias.raw_string).where(SkillAlias.raw_string.in_(["zigzag lang", "quux engine"]))
        )).scalars().all()
        await db.rollback()
        return resolved, cached

    resolved, cached = run(go)

    assert resolved == {"Zigzag Lang": "zigzag", "Quux Engine": None}
    assert cached == ["zigzag lang"]


def test_a_failed_tagging_call_is_tried_again_next_time(seeded, model):
    # Text no keyword matches, so only the model can tag it.
    item = {"key": "p1", "text": "Qqq zzz vvv.", "existing_tags": None}
    model.will(
        api_error(RateLimitError, 429),
        {"results": [{"key": "p1", "tags": ["ownership"]}]},
    )

    async def go(db):
        first = await tag_or_backfill_items(db, [item])
        remembered = len((await db.execute(select(CompetencyTagAlias))).scalars().all())
        second = await tag_or_backfill_items(db, [item])
        await db.rollback()
        return first, remembered, second

    first, remembered, second = run(go)

    assert first == {}
    assert second == {"p1": ["ownership"]}
    assert len(model.requests) == 2
