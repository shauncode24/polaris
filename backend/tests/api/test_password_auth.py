"""Email sign-up and password sign-in, end to end on the real database."""
import uuid

import pytest
from sqlalchemy import select

from app.models.facts import User
from tests.api.test_evidence import run

PASSWORD = "correct-horse-9"


def new_email() -> str:
    return f"{uuid.uuid4().hex}@example.com"


def register(client, email, password=PASSWORD):
    return client.post("/auth/register", json={"first_name": "Noor", "email": email, "password": password})


def login(client, email, password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def stored_hash(email) -> str:
    async def go(db):
        return await db.scalar(select(User.password_hash).where(User.email == email))
    return run(go)


def test_a_new_account_can_sign_in(client, seeded):
    email = new_email()

    created = register(client, email)
    signed_in = login(client, email)

    assert created.status_code == 200, created.text[:300]
    assert signed_in.status_code == 200, signed_in.text[:300]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {signed_in.json()['access_token']}"})
    assert me.json()["email"] == email
    assert stored_hash(email).startswith("$2b$") and PASSWORD not in stored_hash(email)


def test_a_wrong_password_is_refused(client, seeded):
    email = new_email()
    register(client, email)

    response = login(client, email, "correct-horse-8")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password."}


@pytest.mark.parametrize("password", ["x" * 100, "é" * 60], ids=["long", "long non-ascii"])
def test_a_password_longer_than_bcrypt_reads_still_works(client, seeded, password):
    email = new_email()

    assert register(client, email, password).status_code == 200
    assert login(client, email, password).status_code == 200
    assert login(client, email, "y" + password[1:]).status_code == 401


@pytest.mark.parametrize("value", ["not-a-hash", None], ids=["unreadable", "none (Google account)"])
def test_an_account_without_a_usable_password_is_refused(client, seeded, value):
    email = new_email()

    async def add(db):
        db.add(User(name="Gil", email=email, password_hash=value, auth_provider="google",
                    target_roles=[], target_companies=[]))
        await db.commit()
    run(add)

    assert login(client, email).status_code == 401
