"""The links emailed to confirm an address or set a new password.

A link carries a signed token, so nothing about it is stored. A reset token also
carries a fingerprint of the password it replaces: once the password changes, it
and every other reset link sent before stop working.

The token is put after `#`, which browsers don't send to servers, so it stays out
of their logs.
"""
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import mail
from app.core.rate_limit import SlidingWindow
from app.core.security import hash_password
from app.core.settings import settings
from app.models.facts import User
from app.services.auth.sessions import end_all_sessions

CONFIRM_HOURS = 48
RESET_HOURS = 1

_CONFIRM = "confirm-email"
_RESET = "reset-password"

# However it is asked for, one address is sent only so many of each email an
# hour, so nobody can use the app to flood an inbox.
per_address = SlidingWindow(limit=3, window=60 * 60)

Sent = Literal["sent", "limited", "failed"]


def _sign(user_id, use: str, hours: float, **claims) -> str:
    payload = {
        "sub": str(user_id), "use": use,
        "exp": datetime.now(timezone.utc) + timedelta(hours=hours), **claims,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _read(token: str, use: str) -> tuple[UUID, dict] | None:
    """The user and claims of an unexpired token made for `use`, or None."""
    try:
        claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if claims.get("use") != use:
            return None
        return UUID(claims["sub"]), claims
    except (JWTError, KeyError, ValueError):
        return None


def _fingerprint(password_hash: str | None) -> str:
    message = f"password:{password_hash or ''}".encode()
    return hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).hexdigest()[:32]


def confirmation_token(user: User) -> str:
    return _sign(user.id, _CONFIRM, CONFIRM_HOURS, email=user.email)


def reset_token(user: User) -> str:
    return _sign(user.id, _RESET, RESET_HOURS, password=_fingerprint(user.password_hash))


async def confirm_email(db: AsyncSession, token: str) -> bool:
    """Marks the address confirmed. Following the link again is harmless."""
    read = _read(token, _CONFIRM)
    if read is None:
        return False
    user_id, claims = read
    user = await db.get(User, user_id)
    if user is None or user.email != claims.get("email"):
        return False
    if user.email_verified_at is None:
        user.email_verified_at = datetime.now(timezone.utc)
        await db.commit()
    return True


async def reset_password(db: AsyncSession, token: str, new_password: str) -> bool:
    """Sets the new password and signs the account out everywhere. Using the
    link also shows that the address is the user's.
    """
    read = _read(token, _RESET)
    if read is None:
        return False
    user_id, claims = read
    # Locked, so that a link sent twice at once works once.
    user = await db.scalar(
        select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
    )
    if user is None or claims.get("password") != _fingerprint(user.password_hash):
        return False
    user.password_hash = hash_password(new_password)
    user.email_verified_at = user.email_verified_at or datetime.now(timezone.utc)
    await end_all_sessions(db, user.id)
    await db.commit()
    return True


# --- the emails --------------------------------------------------------------
# They never include a name or anything else someone typed: anyone can sign up
# with another person's address, and so choose what would be sent there.

async def _send(to: str, subject: str, body: str) -> Sent:
    if per_address.hit((subject, to.lower())) is not None:
        return "limited"
    return "sent" if await mail.send(to, subject, body) else "failed"


async def send_confirmation(to: str, token: str) -> Sent:
    link = f"{settings.frontend_origin}/confirm-email#token={token}"
    return await _send(to, "Confirm your email address for Polaris", (
        "Someone, hopefully you, signed up for Polaris with this address.\n\n"
        f"Confirm that it is yours:\n{link}\n\n"
        f"The link works for {CONFIRM_HOURS} hours. If you didn't sign up, ignore this email: "
        "don't open the link.\n"
    ))


async def send_password_reset(to: str, token: str) -> Sent:
    link = f"{settings.frontend_origin}/reset-password#token={token}"
    return await _send(to, "Set a new password for Polaris", (
        "Someone, hopefully you, asked to set a new password for your Polaris account.\n\n"
        f"Choose one here:\n{link}\n\n"
        f"The link works once, for {RESET_HOURS} hour. If you didn't ask for it, ignore this email: "
        "your password has not changed.\n"
    ))
