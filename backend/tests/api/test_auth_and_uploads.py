"""Token handling and upload validation. None of these reach the LLM:
every request here is rejected before ingestion starts.
"""
from jose import jwt

from app.core.settings import settings


def test_download_requires_the_auth_header_not_a_query_token(client, seeded, alice_headers):
    token = alice_headers["Authorization"].removeprefix("Bearer ")
    response = client.get(f"/resume/download?token={token}")
    assert response.status_code == 401


def test_download_with_header_reaches_the_route(client, alice_headers):
    # Alice's seeded resume has no stored PDF, so a working route answers 404 (not 401).
    response = client.get("/resume/download", headers=alice_headers)
    assert response.status_code == 404
    assert "PDF not stored" in response.json()["detail"]


def test_token_with_a_non_uuid_subject_is_unauthorised_not_a_server_error(client):
    forged = jwt.encode({"sub": "not-a-uuid"}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_token_for_a_deleted_user_is_unauthorised(client):
    ghost = jwt.encode(
        {"sub": "00000000-0000-0000-0000-00000000dead"}, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {ghost}"})
    assert response.status_code == 401


def test_corrupt_pdf_resume_upload_is_a_400(client, bob_headers):
    response = client.post(
        "/resume/upload",
        files={"file": ("broken.pdf", b"%PDF-1.4\nthis is not a real pdf", "application/pdf")},
        headers=bob_headers,
    )
    assert response.status_code == 400


def test_non_pdf_resume_upload_is_a_400(client, bob_headers):
    response = client.post(
        "/resume/upload",
        files={"file": ("notes.txt", b"just text", "text/plain")},
        headers=bob_headers,
    )
    assert response.status_code == 400


def test_corrupt_pdf_job_upload_is_a_400(client, bob_headers):
    response = client.post(
        "/job-intelligence/analyze-pdf",
        files={"file": ("job.pdf", b"%PDF-1.4\nnot a pdf", "application/pdf")},
        headers=bob_headers,
    )
    assert response.status_code == 400
