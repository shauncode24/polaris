"""Downloading the tailored resume, through the API. Real database; stand-in model."""
import io
from urllib.parse import unquote

import pytest

from app.core import llm
from app.services.resume.docx_parser import extract_text_from_docx
from app.services.resume.pdf_parser import extract_text_from_pdf
from tests.api.test_evidence import auth
from tests.api.test_resume_editor import ORIGINALS, decide, lines, made, patch  # noqa: F401 (made is a fixture)
from tests.llm_stub import model  # noqa: F401 (model is a fixture)

READERS = {"pdf": extract_text_from_pdf, "docx": extract_text_from_docx}


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    monkeypatch.setattr(llm, "API_KEY", "test-key")


def download(client, user, job, file_format, version=1):
    return client.get(
        f"/tailored-resumes/{job}/versions/{version}/export?format={file_format}", headers=auth(user.id),
    )


def text_of(response, file_format) -> str:
    assert response.status_code == 200, response.text[:300]
    return READERS[file_format](io.BytesIO(response.content))


@pytest.mark.parametrize(("file_format", "media_type", "start"), [
    ("pdf", "application/pdf", b"%PDF"),
    ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"PK"),
])
def test_a_version_downloads_as_a_named_file(client, made, file_format, media_type, start):
    user, job, _role, _view = made

    response = download(client, user, job, file_format)

    assert response.status_code == 200, response.text[:300]
    assert response.content.startswith(start)
    assert response.headers["content-type"] == media_type
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert unquote(disposition.split("filename*=UTF-8''")[1]) == f"Sam Rivera - Globex - resume v1.{file_format}"
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("file_format", READERS)
def test_the_download_holds_the_saved_choices(client, made, file_format):
    user, job, _role, view = made
    clean = lines(view)[0]

    before = text_of(download(client, user, job, file_format), file_format)
    assert ORIGINALS[0] in before and "PostgreSQL queries" not in before and "Redis" not in before

    decide(client, user, job, clean, decision="accepted")
    after = text_of(download(client, user, job, file_format), file_format)

    assert "Tuned PostgreSQL queries." in after and ORIGINALS[1] in after and "Redis" not in after


def test_the_browser_may_read_the_file_name(client, made):
    user, job, _role, _view = made

    response = client.get(
        f"/tailored-resumes/{job}/versions/1/export?format=pdf",
        headers={**auth(user.id), "Origin": "http://localhost:5173"},
    )

    assert "content-disposition" in response.headers.get("access-control-expose-headers", "").lower()


def test_a_character_the_pdf_cannot_show_is_explained(client, made):
    user, job, _role, view = made
    decide(client, user, job, lines(view)[0], edited="Shipped it 🚀")

    refused = download(client, user, job, "pdf")

    assert refused.status_code == 422
    assert "🚀" in refused.json()["detail"] and "Word file" in refused.json()["detail"]
    assert "Shipped it 🚀" in text_of(download(client, user, job, "docx"), "docx")


@pytest.mark.parametrize("query", ["", "?format=html", "?format="])
def test_only_the_two_formats_exist(client, made, query):
    user, job, _role, _view = made

    response = client.get(f"/tailored-resumes/{job}/versions/1/export{query}", headers=auth(user.id))

    assert response.status_code == 422


def test_a_missing_version_or_another_users_resume_gives_nothing(client, made):
    user, job, _role, _view = made
    from tests.api.test_resume_selection import new_user

    assert download(client, user, job, "pdf", version=2).status_code == 404
    assert download(client, new_user(), job, "pdf").status_code == 404
    assert client.get(f"/tailored-resumes/{job}/versions/1/export?format=pdf").status_code == 401
