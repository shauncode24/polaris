"""Signed-in browsers and their refresh tokens.

An access token is short-lived and stored nowhere. To get a new one the browser
sends its refresh token, in a cookie that scripts can't read, and every use
replaces that token with the next one.

A refresh token is `session.generation.signature`, so no token is stored: only
which generation of each session is current. An earlier generation coming back
means two parties hold copies of the session, so one of them stole it; nothing
tells which, so the session ends. The exception is the token replaced within the
last `REUSE_GRACE`: two requests may send it at once, and the reply carrying its
successor may have been lost. It is answered with the current token.
"""
import base64
import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import settings
from app.models.auth_session import AuthSession
from app.models.facts import User

logger = logging.getLogger(__name__)

REUSE_GRACE = timedelta(seconds=30)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lifetime() -> timedelta:
    """How long a session lasts after it was last used."""
    return timedelta(days=settings.refresh_token_days)


def _signature(session_id: uuid.UUID, generation: int) -> str:
    # The prefix keeps this apart from anything else signed with the same secret.
    message = f"refresh-token:{session_id.hex}:{generation}".encode()
    digest = hmac.new(settings.jwt_secret.encode(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _token(session_id: uuid.UUID, generation: int) -> str:
    return f"{session_id.hex}.{generation}.{_signature(session_id, generation)}"


def _read(token: str) -> tuple[uuid.UUID, int] | None:
    """The session and generation a token we issued names, or None."""
    try:
        session_hex, generation_text, signature = token.split(".")
        session_id, generation = uuid.UUID(hex=session_hex), int(generation_text)
    except ValueError:
        return None
    if not hmac.compare_digest(signature.encode(), _signature(session_id, generation).encode()):
        return None
    return session_id, generation


async def start_session(db: AsyncSession, user_id) -> str:
    """Records a new sign-in and returns its first refresh token."""
    now = _now()
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user_id, AuthSession.expires_at <= now))
    session_id = uuid.uuid4()
    db.add(AuthSession(
        id=session_id, user_id=user_id, generation=1,
        rotated_at=now, expires_at=now + _lifetime(), created_at=now,
    ))
    await db.commit()
    return _token(session_id, 1)


async def renew_session(db: AsyncSession, token: str) -> tuple[User, str] | None:
    """The session's user and the refresh token to use next, or None if this one
    is no good.
    """
    named = _read(token)
    if named is None:
        return None
    session_id, generation = named
    # Locked, so that two requests renewing one session take turns.
    session = await db.scalar(
        select(AuthSession).where(AuthSession.id == session_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if session is None:
        return None

    now = _now()
    current = generation == session.generation
    just_replaced = generation == session.generation - 1 and now - session.rotated_at <= REUSE_GRACE
    expired = session.expires_at <= now
    if expired or not (current or just_replaced):
        if not expired:
            logger.warning(
                "A replaced refresh token was used again: ending session %s of user %s",
                session.id, session.user_id,
            )
        await db.delete(session)
        await db.commit()
        return None

    if current:
        session.generation += 1
        session.rotated_at = now
    session.expires_at = now + _lifetime()
    user = await db.get(User, session.user_id)
    next_token = _token(session.id, session.generation)
    await db.commit()
    return user, next_token


async def end_all_sessions(db: AsyncSession, user_id) -> None:
    """Signs the user out of every browser. The caller commits."""
    await db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


async def end_session(db: AsyncSession, token: str) -> None:
    """Signs out the session a token belongs to, however old the token."""
    named = _read(token)
    if named is None:
        return
    await db.execute(delete(AuthSession).where(AuthSession.id == named[0]))
    await db.commit()
