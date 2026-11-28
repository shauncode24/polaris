"""Sending email over SMTP, with a stand-in for the server, and its settings."""
import asyncio
import logging
import smtplib
import ssl

import pytest

from app.core import mail
from app.core.settings import ConfigurationError, Settings, settings

PASSWORD = "app-password"


class Server:
    """Records what the app does with an SMTP connection."""
    made: list = []
    fail_with = None

    def __init__(self, host, port, timeout=None, context=None):
        self.address, self.timeout, self.context = (host, port), timeout, context
        self.steps, self.sent = [], []
        Server.made.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *error):
        self.steps.append("quit")

    def starttls(self, context=None):
        self.context = context
        self.steps.append("starttls")

    def login(self, username, password):
        self.steps.append(("login", username, password))

    def send_message(self, message):
        if Server.fail_with:
            raise Server.fail_with
        self.steps.append("send")
        self.sent.append(message)


class EncryptedServer(Server):
    pass


@pytest.fixture(autouse=True)
def logged(monkeypatch):
    # Building the test database's schema switches existing loggers off.
    monkeypatch.setattr(mail.logger, "disabled", False)


@pytest.fixture
def smtp(monkeypatch):
    Server.made, Server.fail_with = [], None
    monkeypatch.setattr(smtplib, "SMTP", Server)
    monkeypatch.setattr(smtplib, "SMTP_SSL", EncryptedServer)
    for name, value in {
        "smtp_host": "smtp.example.com", "smtp_port": 587, "smtp_security": "starttls",
        "smtp_username": "polaris@example.com", "smtp_password": PASSWORD,
        "mail_from": "Polaris <polaris@example.com>",
    }.items():
        monkeypatch.setattr(settings, name, value)
    return Server


def send(to="noor@example.com"):
    return asyncio.run(mail.send(to, "A subject", "A body with a link"))


def test_an_email_goes_over_an_encrypted_checked_connection(smtp):
    assert send() is True

    [server] = smtp.made
    assert server.address == ("smtp.example.com", 587) and server.timeout
    assert server.steps == ["starttls", ("login", "polaris@example.com", PASSWORD), "send", "quit"]
    assert server.context.verify_mode == ssl.CERT_REQUIRED and server.context.check_hostname
    [message] = server.sent
    assert (message["To"], message["From"], message["Subject"]) == (
        "noor@example.com", "Polaris <polaris@example.com>", "A subject")
    assert message.get_content().strip() == "A body with a link"


def test_ssl_is_encrypted_from_the_start(smtp, monkeypatch):
    monkeypatch.setattr(settings, "smtp_security", "ssl")
    assert send() is True
    [server] = smtp.made
    assert isinstance(server, EncryptedServer) and "starttls" not in server.steps
    assert server.context.verify_mode == ssl.CERT_REQUIRED


def test_a_server_without_a_user_name_is_not_logged_in_to(smtp, monkeypatch):
    monkeypatch.setattr(settings, "smtp_security", "none")
    monkeypatch.setattr(settings, "smtp_username", "")
    assert send() is True
    assert smtp.made[0].steps == ["send", "quit"]


@pytest.mark.parametrize("error", [
    smtplib.SMTPRecipientsRefused({"noor@example.com": (550, b"no such user noor@example.com")}),
    smtplib.SMTPAuthenticationError(535, b"bad password"),
    smtplib.SMTPNotSupportedError("STARTTLS not offered"),
    ConnectionRefusedError(),
    TimeoutError(),
], ids=["recipient", "password", "no encryption", "refused", "timeout"])
def test_a_failure_is_reported_without_the_address_or_the_link(smtp, caplog, error):
    smtp.fail_with = error
    with caplog.at_level(logging.DEBUG):
        assert send() is False
    assert type(error).__name__ in caplog.text
    assert "noor@example.com" not in caplog.text and "link" not in caplog.text


def test_without_a_server_the_email_is_written_to_the_log(monkeypatch, caplog):
    monkeypatch.setattr(settings, "smtp_host", "")
    with caplog.at_level(logging.WARNING):
        assert send() is True
    assert "noor@example.com" in caplog.text and "A body with a link" in caplog.text


# --- settings ----------------------------------------------------------------

@pytest.fixture
def env(monkeypatch):
    def use(**values):
        for name, value in values.items():
            monkeypatch.setenv(name, value)
        return Settings()
    return use


def test_the_defaults_suit_a_hosted_service(env):
    made = env(SMTP_HOST="smtp.example.com", SMTP_USERNAME="polaris@example.com")
    assert (made.smtp_security, made.smtp_port, made.mail_from) == ("starttls", 587, "polaris@example.com")
    assert env(SMTP_SECURITY="SSL").smtp_port == 465
    assert env(SMTP_PORT="2525").smtp_port == 2525


@pytest.mark.parametrize("named, values", [
    ("MAIL_FROM", {"SMTP_HOST": "smtp.example.com", "SMTP_USERNAME": "apikey"}),
    ("SMTP_SECURITY", {"SMTP_SECURITY": "tls"}),
    ("SMTP_SECURITY", {"SMTP_HOST": "localhost", "SMTP_SECURITY": "none", "SMTP_USERNAME": "a@b.test"}),
    ("SMTP_PORT", {"SMTP_PORT": "0"}),
    ("SMTP_HOST", {"FRONTEND_ORIGIN": "https://polaris.example"}),
    ("REQUIRE_CONFIRMED_EMAIL", {"REQUIRE_CONFIRMED_EMAIL": "no thanks"}),
], ids=["no sender", "unknown security", "password in the clear", "port", "https without email", "flag"])
def test_email_settings_that_would_not_work_stop_the_server(env, named, values):
    with pytest.raises(ConfigurationError, match=named):
        env(**values)


def test_a_confirmed_address_is_required_unless_switched_off(env, monkeypatch):
    monkeypatch.delenv("REQUIRE_CONFIRMED_EMAIL")
    assert Settings().require_confirmed_email is True
    assert env(REQUIRE_CONFIRMED_EMAIL="").require_confirmed_email is True
    assert env(REQUIRE_CONFIRMED_EMAIL="False").require_confirmed_email is False
