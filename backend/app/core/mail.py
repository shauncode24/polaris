"""Sends the app's emails over SMTP, which any mail service offers.

Without SMTP_HOST, allowed only while the app is served over plain http (local
development), an email is written to the server log instead, links and all.
"""
import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.settings import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 20


def _deliver(message: EmailMessage) -> None:
    context = ssl.create_default_context()  # checks the server's certificate
    if settings.smtp_security == "ssl":
        server = smtplib.SMTP_SSL(
            settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SECONDS, context=context,
        )
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=TIMEOUT_SECONDS)
    with server:
        if settings.smtp_security == "starttls":
            server.starttls(context=context)  # fails rather than carry on unencrypted
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


async def send(to: str, subject: str, body: str) -> bool:
    """True once the mail service has taken the email."""
    if not settings.smtp_host:
        logger.warning(
            "SMTP_HOST is not set, so this email was not sent.\nTo: %s\nSubject: %s\n\n%s", to, subject, body,
        )
        return True

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    try:
        await asyncio.to_thread(_deliver, message)  # off the event loop: smtplib blocks
    except (smtplib.SMTPException, OSError) as e:
        # The error's text can hold the address, which doesn't belong in a log.
        logger.error(
            "Email '%s' was not sent: %s (SMTP code %s)",
            subject, type(e).__name__, getattr(e, "smtp_code", "none"),
        )
        return False
    return True
