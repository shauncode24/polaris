"""Confirming an email address, resetting a password, and what waits for a
confirmed address. Real database; email is captured instead of sent.
"""
import asyncio
import re
import time
import uuid
from datetime import datetime, timezone

import pytest
from google.oauth2 import id_token
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import auth as auth_api
from app.core import llm, mail
from app.core.security import hash_password
from app.core.settings import settings
from app.models.auth_session import AuthSession
from app.models.facts import User
from app.services.auth import email_links
from tests.api.conftest import _new_engine
from tests.api.test_evidence import run
from tests.api.test_job_library import add_job
from tests.api.test_llm_budget import job_count, on_behalf_of, used
from tests.api.test_password_auth import PASSWORD, new_email
from tests.api.test_sessions import Browser
from tests.llm_stub import model, reply  # noqa: F401 (model is a fixture)

NEW_PASSWORD = "a-different-horse-4"


class Outbox(list):
    works = True

    async def send(self, to, subject, body):
        if self.works:
            self.append({"to": to, "subject": subject, "body": body})
        return self.works

    def to(self, address):
        return [message for message in self if message["to"] == address]

    def token(self, address, page):
        """The token in the newest link to `page` sent to the address."""
        links = [re.search(rf"{page}#token=(\S+)", message["body"]) for message in self.to(address)]
        return [link for link in links if link][-1].group(1)


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    box = Outbox()
    monkeypatch.setattr(mail, "send", box.send)
    email_links.per_address.clear()
    yield box
    email_links.per_address.clear()


@pytest.fixture
def required(monkeypatch):
    monkeypatch.setattr(settings, "require_confirmed_email", True)


@pytest.fixture
def newcomer(client, seeded):
    """A browser signed in to a new, unconfirmed account."""
    browser = Browser(client)
    browser.register()
    return browser


def stored(email) -> User:
    async def go(db):
        return await db.scalar(select(User).where(User.email == email))
    return run(go)


def session_count(email) -> int:
    async def go(db):
        result = await db.execute(
            select(AuthSession.id).join(User, User.id == AuthSession.user_id).where(User.email == email))
        return len(result.all())
    return run(go)


def add_user(**values) -> User:
    values.setdefault("email", new_email())

    async def go(db):
        user = User(name="Gil", target_roles=[], target_companies=[], **values)
        db.add(user)
        await db.commit()
        return user
    return run(go)


def headers(browser):
    return {"Authorization": f"Bearer {browser.access}"}


def post(client, path, **body):
    client.cookies.clear()
    return client.post(path, json=body)


def confirm(client, token):
    return post(client, "/auth/email/confirm", token=token)


def forgot(client, email):
    return post(client, "/auth/password/forgot", email=email)


def reset(client, token, password=NEW_PASSWORD):
    return post(client, "/auth/password/reset", token=token, password=password)


def assert_bad_link(response):
    assert (response.status_code, response.json()) == (400, {"detail": auth_api.BAD_LINK})


# --- confirming an address ---------------------------------------------------

def test_signing_up_sends_a_confirmation_link_to_the_address(newcomer, outbox):
    [message] = outbox.to(newcomer.email)
    assert message["subject"] == "Confirm your email address for Polaris"
    assert f"{settings.frontend_origin}/confirm-email#token=" in message["body"]


def test_no_email_carries_what_someone_typed(client, seeded, outbox):
    email = new_email()
    post(client, "/auth/register", first_name="Visit evil.example", email=email, password=PASSWORD)
    forgot(client, email)
    assert len(outbox.to(email)) == 2
    assert not any("evil.example" in message["body"] for message in outbox)


def test_following_the_link_confirms_the_address(client, newcomer, outbox, required):
    assert newcomer.refresh().json()["user"]["needs_email_confirmation"] is True
    token = outbox.token(newcomer.email, "confirm-email")

    assert confirm(client, token).status_code == 204
    first = stored(newcomer.email).email_verified_at
    assert first is not None
    assert newcomer.refresh().json()["user"]["needs_email_confirmation"] is False
    assert confirm(client, token).status_code == 204  # clicked twice
    assert stored(newcomer.email).email_verified_at == first


def test_a_failing_mail_service_does_not_stop_sign_up(client, seeded, outbox):
    outbox.works = False
    assert Browser(client).register().status_code == 200


def signed(claims):
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.mark.parametrize("make", [
    lambda user: "nonsense",
    lambda user: email_links.confirmation_token(user)[:-3] + "abc",
    lambda user: signed({"sub": str(user.id), "use": "confirm-email", "email": user.email,
                         "exp": time.time() - 5}),
    lambda user: jwt.encode({"sub": str(user.id), "use": "confirm-email", "email": user.email,
                             "exp": time.time() + 60}, "another secret", algorithm="HS256"),
    lambda user: email_links.reset_token(user),
    lambda user: signed({"sub": str(user.id), "use": "access", "exp": time.time() + 60}),
    lambda user: signed({"sub": str(user.id), "use": "confirm-email", "email": "old@example.com",
                         "exp": time.time() + 60}),
    lambda user: signed({"sub": str(uuid.uuid4()), "use": "confirm-email", "email": user.email,
                         "exp": time.time() + 60}),
    lambda user: signed({"use": "confirm-email", "exp": time.time() + 60}),
], ids=["nonsense", "altered", "expired", "forged", "reset link", "access token",
        "another address", "no such user", "no user"])
def test_only_a_good_confirmation_link_confirms(client, newcomer, make):
    assert_bad_link(confirm(client, make(stored(newcomer.email))))
    assert stored(newcomer.email).email_verified_at is None


@pytest.mark.parametrize("token_of", [
    lambda newcomer, outbox: outbox.token(newcomer.email, "confirm-email"),
    lambda newcomer, outbox: newcomer.access,
], ids=["confirmation link", "access token"])
def test_no_other_token_resets_a_password(client, newcomer, outbox, token_of):
    assert_bad_link(reset(client, token_of(newcomer, outbox)))
    assert newcomer.sign_in(newcomer.email).status_code == 200


def test_an_emailed_token_does_not_sign_anyone_in(newcomer, outbox):
    token = outbox.token(newcomer.email, "confirm-email")
    assert newcomer.me(token).status_code == 401


# --- sending it again --------------------------------------------------------

def resend(client, browser):
    return client.post("/auth/email/resend", headers=headers(browser))


def test_the_link_can_be_sent_again(client, newcomer, outbox):
    response = resend(client, newcomer)
    assert (response.status_code, response.json()) == (200, {"detail": auth_api.CONFIRMATION_SENT})
    assert len(outbox.to(newcomer.email)) == 2
    assert confirm(client, outbox.token(newcomer.email, "confirm-email")).status_code == 204


def test_nothing_is_sent_for_a_confirmed_address(client, newcomer, outbox):
    confirm(client, outbox.token(newcomer.email, "confirm-email"))
    response = resend(client, newcomer)
    assert response.json() == {"detail": auth_api.ALREADY_CONFIRMED}
    assert len(outbox.to(newcomer.email)) == 1


def test_an_address_is_only_sent_so_many_an_hour(client, newcomer, outbox):
    assert [resend(client, newcomer).status_code for _ in range(2)] == [200, 200]
    refused = resend(client, newcomer)
    assert (refused.status_code, refused.json()) == (429, {"detail": auth_api.TOO_MANY_EMAILS})
    assert len(outbox.to(newcomer.email)) == 3  # the one at sign-up counts


def test_the_user_hears_if_it_could_not_be_sent(client, newcomer, outbox):
    outbox.works = False
    response = resend(client, newcomer)
    assert (response.status_code, response.json()) == (503, {"detail": auth_api.EMAIL_FAILED})


def test_only_a_signed_in_user_can_ask_for_it(client, seeded, outbox):
    assert client.post("/auth/email/resend").status_code == 401
    assert outbox == []


# --- forgotten passwords -----------------------------------------------------

def test_asking_for_a_reset_answers_the_same_with_or_without_an_account(client, newcomer, outbox):
    known, unknown = forgot(client, newcomer.email), forgot(client, new_email())

    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"detail": auth_api.RESET_REQUESTED}
    assert [message["to"] for message in outbox[1:]] == [newcomer.email]
    assert f"{settings.frontend_origin}/reset-password#token=" in outbox[-1]["body"]


def test_the_address_may_be_typed_with_other_capitals(client, newcomer, outbox):
    forgot(client, newcomer.email.upper())
    assert outbox[-1]["to"] == newcomer.email


def test_repeated_requests_do_not_flood_an_inbox(client, newcomer, outbox):
    answers = [forgot(client, newcomer.email) for _ in range(6)]
    assert {answer.status_code for answer in answers} == {200}
    assert len([m for m in outbox.to(newcomer.email) if "reset-password" in m["body"]]) == 3


def test_a_new_password_replaces_the_old_one(client, newcomer, outbox):
    forgot(client, newcomer.email)
    assert reset(client, outbox.token(newcomer.email, "reset-password")).status_code == 204

    assert newcomer.sign_in(newcomer.email, PASSWORD).status_code == 401
    assert newcomer.sign_in(newcomer.email, NEW_PASSWORD).status_code == 200


def test_a_reset_signs_the_account_out_everywhere_and_confirms_the_address(client, newcomer, outbox):
    laptop = Browser(client)
    laptop.sign_in(newcomer.email)
    other = Browser(client)
    other.register()
    forgot(client, newcomer.email)

    reset(client, outbox.token(newcomer.email, "reset-password"))

    assert session_count(newcomer.email) == 0
    assert newcomer.refresh().status_code == laptop.refresh().status_code == 401
    assert other.refresh().status_code == 200
    assert stored(newcomer.email).email_verified_at is not None


def test_a_reset_link_works_once_and_ends_the_earlier_ones(client, newcomer, outbox):
    forgot(client, newcomer.email)
    earlier = outbox.token(newcomer.email, "reset-password")
    time.sleep(1.1)  # so the second differs
    forgot(client, newcomer.email)
    later = outbox.token(newcomer.email, "reset-password")
    assert earlier != later

    assert reset(client, later).status_code == 204
    assert_bad_link(reset(client, later, "yet-another-one-7"))
    assert_bad_link(reset(client, earlier, "yet-another-one-7"))
    assert newcomer.sign_in(newcomer.email, NEW_PASSWORD).status_code == 200


def test_a_link_used_twice_at_once_works_once(newcomer):
    token = email_links.reset_token(stored(newcomer.email))

    async def go():
        engine = _new_engine()
        factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

        async def use(password):
            async with factory() as db:
                return await email_links.reset_password(db, token, password)
        try:
            return await asyncio.gather(*(use(f"password-number-{n}") for n in range(4)))
        finally:
            await engine.dispose()

    assert sorted(asyncio.run(go())) == [False, False, False, True]


def test_an_expired_reset_link_is_refused(client, newcomer, monkeypatch):
    monkeypatch.setattr(email_links, "RESET_HOURS", -1)
    assert_bad_link(reset(client, email_links.reset_token(stored(newcomer.email))))
    assert newcomer.sign_in(newcomer.email).status_code == 200


def test_a_password_too_short_is_refused_and_the_link_still_works(client, newcomer, outbox):
    forgot(client, newcomer.email)
    token = outbox.token(newcomer.email, "reset-password")

    refused = reset(client, token, "short")
    assert refused.status_code == 422
    assert "at least 8 characters" in refused.json()["detail"][0]["msg"]
    assert reset(client, token).status_code == 204


def test_an_account_without_a_password_can_set_one(client, seeded, outbox):
    user = add_user(auth_provider="google", google_id=uuid.uuid4().hex)
    forgot(client, user.email)
    assert reset(client, outbox.token(user.email, "reset-password")).status_code == 204
    assert Browser(client).sign_in(user.email, NEW_PASSWORD).status_code == 200


# --- what waits for a confirmed address --------------------------------------

def ask():
    return llm.llm_json(llm.Prompt("system", "user"), dict, label="test", fallback=lambda: {"made": "up"})


def test_an_unconfirmed_user_cannot_start_ai_work(client, newcomer, required, model):
    user = stored(newcomer.email)
    for path, body in [
        ("/linkedin/ingest", {"raw_text": "Engineer at Acme"}),
        ("/interview/ask", {"question": "Tell me about yourself"}),
        ("/identity/refresh", None),
    ]:
        response = client.start("POST", path, headers=headers(newcomer), json=body)
        assert response.status_code == 403, path
        assert response.json()["detail"].startswith("Confirm your email address")
    assert job_count(user) == 0 and model.requests == []


def test_no_call_reaches_the_model_even_where_there_is_a_fallback(newcomer, required, model):
    user = stored(newcomer.email)
    with pytest.raises(llm.LLMUnconfirmedError):
        on_behalf_of(user, ask)
    assert model.requests == [] and used(user) == 0


def test_work_that_manages_without_ai_still_runs_and_says_why(client, newcomer, required, model):
    user = stored(newcomer.email)
    job = add_job(user, "Backend Engineer", required=["python"])

    response = client.post(f"/interview/kits/{job}", headers=headers(newcomer))

    assert response.status_code == 200, response.text
    assert "Confirm your email address" in response.json()["kit"]["notice"]
    assert model.requests == []


def test_pages_still_load_for_an_unconfirmed_user(client, newcomer, required):
    for path in ("/profile/data", "/resume/workspace", "/job-intelligence", "/github/workspace"):
        assert client.get(path, headers=headers(newcomer)).status_code == 200, path


def test_ai_works_once_the_address_is_confirmed(client, newcomer, outbox, required, model):
    confirm(client, outbox.token(newcomer.email, "confirm-email"))
    model.will({"answer": "yes"})
    assert on_behalf_of(stored(newcomer.email), ask).value == {"answer": "yes"}


def test_the_rule_can_be_switched_off(newcomer, model, monkeypatch):
    monkeypatch.setattr(settings, "require_confirmed_email", False)
    model.will({"answer": "yes"})
    assert on_behalf_of(stored(newcomer.email), ask).value == {"answer": "yes"}
    assert newcomer.refresh().json()["user"]["needs_email_confirmation"] is False


# --- Google ------------------------------------------------------------------

def google_sign_in(client, monkeypatch, email, *, verified=True, subject=None):
    claims = {"sub": subject or uuid.uuid4().hex, "email": email, "email_verified": verified,
              "given_name": "Gil"}
    monkeypatch.setattr(settings, "google_client_id", "test-client")
    monkeypatch.setattr(id_token, "verify_oauth2_token", lambda *args, **kwargs: claims)
    client.cookies.clear()
    response = client.post("/auth/google", json={"credential": "stand-in"})
    client.cookies.clear()
    return response


def test_a_new_google_account_is_already_confirmed(client, seeded, monkeypatch, required):
    email = new_email()
    response = google_sign_in(client, monkeypatch, email)
    assert response.status_code == 200, response.text
    assert response.json()["user"]["needs_email_confirmation"] is False
    assert stored(email).email_verified_at is not None


def test_google_takes_an_unconfirmed_account_from_whoever_set_its_password(client, newcomer, monkeypatch):
    """Someone signs up with another person's address, who later uses Google."""
    squatter = newcomer

    response = google_sign_in(client, monkeypatch, squatter.email)

    assert response.status_code == 200
    user = stored(squatter.email)
    assert user.password_hash is None and user.email_verified_at is not None
    assert squatter.refresh().status_code == 401
    assert squatter.sign_in(squatter.email, PASSWORD).status_code == 401
    assert session_count(squatter.email) == 1  # only the Google sign-in


def test_google_leaves_a_confirmed_accounts_password(client, newcomer, outbox, monkeypatch):
    confirm(client, outbox.token(newcomer.email, "confirm-email"))

    assert google_sign_in(client, monkeypatch, newcomer.email).status_code == 200

    assert stored(newcomer.email).google_id is not None
    assert newcomer.refresh().status_code == 200
    assert newcomer.sign_in(newcomer.email).status_code == 200


@pytest.mark.parametrize("verified", [False, "false", None])
def test_an_address_google_has_not_verified_is_not_accepted(client, newcomer, monkeypatch, verified):
    response = google_sign_in(client, monkeypatch, newcomer.email, verified=verified)

    assert response.status_code == 401
    user = stored(newcomer.email)
    assert user.google_id is None and user.password_hash is not None


def test_signing_in_with_google_confirms_an_account_already_linked(client, seeded, monkeypatch):
    subject = uuid.uuid4().hex
    user = add_user(auth_provider="google", google_id=subject, password_hash=hash_password(PASSWORD))

    assert google_sign_in(client, monkeypatch, user.email, subject=subject).status_code == 200

    after = stored(user.email)
    assert after.email_verified_at is not None and after.password_hash is not None
    assert after.email_verified_at <= datetime.now(timezone.utc)
