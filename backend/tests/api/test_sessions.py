"""Short-lived access tokens, and the refresh token that gets new ones. Real
database.
"""
import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie

import pytest
from jose import jwt
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.auth import REFRESH_COOKIE, SESSION_ENDED
from app.core.security import create_access_token
from app.core.settings import settings
from app.models.auth_session import AuthSession
from app.models.facts import User
from app.services.auth import sessions
from tests.api.conftest import _new_engine
from tests.api.test_evidence import run
from tests.api.test_password_auth import PASSWORD, new_email

ORIGIN = "http://localhost:5173"


class Browser:
    """One browser's cookie, kept apart from the shared test client's."""

    def __init__(self, client):
        self.client = client
        self.cookie = None  # the refresh token it holds
        self.email = None
        self.access = None

    def post(self, path, headers=None, **kwargs):
        self.client.cookies.clear()
        headers = dict(headers or {})
        if self.cookie:
            # As bytes: a header may carry any of them.
            headers["Cookie"] = f"{REFRESH_COOKIE}={self.cookie}".encode("latin-1")
        response = self.client.post(path, headers=headers, **kwargs)
        self.client.cookies.clear()
        morsel = set_cookie(response)
        if morsel is not None:
            self.cookie = morsel.value or None
        if response.status_code == 200:
            self.access = response.json()["access_token"]
        return response

    def register(self):
        self.email = new_email()
        response = self.post("/auth/register", json={
            "first_name": "Noor", "email": self.email, "password": PASSWORD,
        })
        assert response.status_code == 200, response.text
        return response

    def sign_in(self, email, password=PASSWORD):
        return self.post("/auth/login", json={"email": email, "password": password})

    def refresh(self, **kwargs):
        return self.post("/auth/refresh", **kwargs)

    def me(self, token=None):
        return self.client.get("/auth/me", headers={"Authorization": f"Bearer {token or self.access}"})


def set_cookie(response):
    for header in response.headers.get_list("set-cookie"):
        cookie = SimpleCookie(header)
        if REFRESH_COOKIE in cookie:
            return cookie[REFRESH_COOKIE]
    return None


@pytest.fixture
def browser(client, seeded):
    browser = Browser(client)
    browser.register()
    return browser


def session_id(token) -> uuid.UUID:
    return uuid.UUID(hex=token.split(".")[0])


def stored(token) -> AuthSession | None:
    async def go(db):
        return await db.get(AuthSession, session_id(token))
    return run(go)


def change(token, **values):
    async def go(db):
        await db.execute(update(AuthSession).where(AuthSession.id == session_id(token)).values(**values))
        await db.commit()
    run(go)


def ago(**duration) -> datetime:
    return datetime.now(timezone.utc) - timedelta(**duration)


def after_the_grace_period(token):
    change(token, rotated_at=ago(seconds=sessions.REUSE_GRACE.total_seconds() + 1))


def assert_ended(response):
    assert (response.status_code, response.json()) == (401, {"detail": SESSION_ENDED})
    cleared = set_cookie(response)
    assert cleared.value == "" and cleared["max-age"] == "0" and cleared["path"] == "/auth"


# --- the access token --------------------------------------------------------

def test_an_access_token_lasts_a_quarter_of_an_hour(browser):
    claims = jwt.get_unverified_claims(browser.access)
    assert 14 * 60 < claims["exp"] - time.time() <= 15 * 60


def test_an_expired_access_token_is_refused_and_a_refresh_gets_a_working_one(browser, monkeypatch):
    monkeypatch.setattr(settings, "access_token_minutes", -1)
    expired = create_access_token(jwt.get_unverified_claims(browser.access)["sub"])
    monkeypatch.undo()
    assert browser.me(expired).status_code == 401

    assert browser.refresh().status_code == 200
    assert browser.me().json()["email"] == browser.email


def test_a_week_long_token_from_before_is_no_longer_accepted(browser):
    old = jwt.encode(
        {"sub": jwt.get_unverified_claims(browser.access)["sub"], "exp": time.time() + 7 * 86400},
        settings.jwt_secret, algorithm=settings.jwt_algorithm,
    )
    assert browser.me(old).status_code == 401


def test_neither_token_works_in_place_of_the_other(browser):
    assert browser.me(browser.cookie).status_code == 401
    browser.cookie = browser.access
    assert_ended(browser.refresh())


# --- the cookie --------------------------------------------------------------

@pytest.mark.parametrize("path", ["register", "login"])
def test_signing_in_sets_a_cookie_that_scripts_cannot_read(browser, path):
    email = new_email() if path == "register" else browser.email
    response = browser.post(f"/auth/{path}", json={"first_name": "Noor", "email": email, "password": PASSWORD})

    cookie = set_cookie(response)
    assert cookie["httponly"] and cookie["path"] == "/auth" and cookie["samesite"] == "lax"
    assert cookie["max-age"] == str(14 * 24 * 60 * 60)
    assert not cookie["secure"]  # the app is on plain http here
    assert response.headers["cache-control"] == "no-store"
    assert cookie.value not in response.text


def test_the_cookie_is_https_only_when_the_app_is(browser, monkeypatch):
    monkeypatch.setattr(settings, "cookie_secure", True)
    assert set_cookie(browser.refresh())["secure"]


def test_a_refused_sign_in_sets_no_cookie(client, browser):
    other = Browser(client)
    response = other.sign_in(browser.email, "wrong-password")
    assert response.status_code == 401 and set_cookie(response) is None


def test_the_database_holds_no_token(browser):
    session = stored(browser.cookie)
    values = {str(getattr(session, column.name)) for column in AuthSession.__table__.columns}
    assert browser.cookie.split(".")[2] not in " ".join(values)


# --- renewing ----------------------------------------------------------------

def test_a_refresh_answers_like_a_sign_in_and_replaces_the_cookie(browser):
    first = browser.cookie
    response = browser.refresh()

    assert response.status_code == 200
    assert response.json()["user"]["email"] == browser.email
    assert {"github_username", "leetcode_username"} <= set(response.json()["user"])
    assert browser.cookie != first and session_id(browser.cookie) == session_id(first)
    assert browser.refresh().status_code == 200  # and so on


def test_each_refresh_extends_the_session(browser):
    change(browser.cookie, expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    browser.refresh()
    assert stored(browser.cookie).expires_at > datetime.now(timezone.utc) + timedelta(days=13)


def test_an_unused_session_expires(browser):
    token = browser.cookie
    change(token, expires_at=ago(seconds=1))
    assert_ended(browser.refresh())
    assert stored(token) is None


def test_no_cookie_means_not_signed_in(client, seeded):
    assert_ended(Browser(client).refresh())


@pytest.mark.parametrize("forge", [
    lambda session, generation, signature: "nonsense",
    lambda session, generation, signature: f"{session}.{generation}.{signature[:-2]}xx",
    lambda session, generation, signature: f"{session}.{int(generation) + 1}.{signature}",
    lambda session, generation, signature: f"{session}.0.{signature}",
    lambda session, generation, signature: f"{uuid.uuid4().hex}.{generation}.{signature}",
    lambda session, generation, signature: f"{session}.{generation}.é",
    lambda session, generation, signature: f"{session}.{'9' * 5000}.{signature}",
], ids=["nonsense", "signature", "later", "earlier", "other session", "not ascii", "huge"])
def test_a_made_up_token_is_refused_and_ends_nothing(browser, forge):
    real = browser.cookie
    forged = forge(*real.split("."))

    browser.cookie = forged
    assert_ended(browser.refresh())
    browser.cookie = forged
    assert browser.post("/auth/logout").status_code == 204
    assert stored(real).generation == 1

    browser.cookie = real
    assert browser.refresh().status_code == 200


def test_signing_out_with_a_made_up_token_ends_nothing(browser):
    real = browser.cookie
    session, generation, _ = real.split(".")
    browser.cookie = f"{session}.{generation}.guess"
    assert browser.post("/auth/logout").status_code == 204
    assert stored(real) is not None


def test_the_token_just_replaced_is_answered_with_the_current_one(browser):
    """Two tabs at once, or a reply that never arrived."""
    first = browser.cookie
    browser.refresh()
    second = browser.cookie

    browser.cookie = first
    for _ in range(3):
        assert browser.refresh().status_code == 200
        assert browser.cookie == second
        browser.cookie = first
    browser.cookie = second
    assert browser.refresh().status_code == 200


def test_a_replaced_token_used_later_ends_the_session(browser):
    stolen = browser.cookie
    browser.refresh()
    current = browser.cookie
    after_the_grace_period(current)

    browser.cookie = stolen
    assert_ended(browser.refresh())
    browser.cookie = current  # whoever holds the newest is signed out too
    assert_ended(browser.refresh())
    assert stored(current) is None


def test_a_token_replaced_twice_ends_the_session_however_soon(browser):
    stolen = browser.cookie
    browser.refresh()
    browser.refresh()
    current = browser.cookie

    browser.cookie = stolen
    assert_ended(browser.refresh())
    assert stored(current) is None


def test_two_renewals_at_the_same_moment_both_get_the_next_token(browser):
    token = browser.cookie

    async def go():
        engine = _new_engine()
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        async def renew():
            async with factory() as db:
                return await sessions.renew_session(db, token)
        try:
            return await asyncio.gather(*(renew() for _ in range(5)))
        finally:
            await engine.dispose()

    renewed = asyncio.run(go())
    assert all(result is not None for result in renewed)
    assert len({next_token for _, next_token in renewed}) == 1
    assert stored(token).generation == 2


# --- signing out -------------------------------------------------------------

def test_signing_out_ends_the_session_and_clears_the_cookie(browser):
    token = browser.cookie
    response = browser.post("/auth/logout")

    assert response.status_code == 204
    assert set_cookie(response).value == "" and browser.cookie is None
    assert stored(token) is None
    browser.cookie = token
    assert_ended(browser.refresh())


def test_signing_out_with_an_old_token_still_ends_the_session(browser):
    old = browser.cookie
    browser.refresh()
    current = browser.cookie
    browser.cookie = old
    assert browser.post("/auth/logout").status_code == 204
    assert stored(current) is None


def test_signing_out_without_a_session_is_fine(client, seeded):
    assert Browser(client).post("/auth/logout").status_code == 204


def test_signing_out_one_browser_leaves_the_others_signed_in(client, browser):
    laptop = Browser(client)
    laptop.sign_in(browser.email)
    browser.post("/auth/logout")
    assert laptop.refresh().status_code == 200


def test_signing_in_again_ends_the_sign_in_it_replaces(client, browser):
    first = browser.cookie
    other = Browser(client)
    other.register()
    browser.sign_in(other.email)  # someone else, same browser

    assert stored(first) is None
    assert browser.refresh().json()["user"]["email"] == other.email


def test_signing_in_clears_out_expired_sessions(client, browser):
    abandoned = browser.cookie
    change(abandoned, expires_at=ago(days=1))
    Browser(client).sign_in(browser.email)
    assert stored(abandoned) is None


def test_deleting_a_user_deletes_their_sessions(browser):
    token = browser.cookie

    async def go(db):
        await db.execute(delete(User).where(User.email == browser.email))
        await db.commit()
        return await db.scalar(select(AuthSession.id).where(AuthSession.id == session_id(token)))
    assert run(go) is None
    assert_ended(browser.refresh())


# --- other sites -------------------------------------------------------------

@pytest.mark.parametrize("path", ["/auth/refresh", "/auth/logout"])
@pytest.mark.parametrize("origin", ["https://evil.example", "http://localhost:3000", "null"])
def test_another_site_cannot_use_the_cookie(browser, path, origin):
    token = browser.cookie
    response = browser.post(path, headers={"Origin": origin})

    assert response.status_code == 403
    assert browser.cookie == token and stored(token).generation == 1


def test_the_app_can_use_the_cookie_across_ports(browser):
    response = browser.refresh(headers={"Origin": ORIGIN})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
