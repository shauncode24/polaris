from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.core.settings import settings
from app.models.facts import User


class AuthError(Exception):
    """Raised for any user-facing auth failure (bad credentials, duplicate
    email, invalid Google token) — callers translate this into a 400/401
    response instead of a 500, same graceful-degradation philosophy as
    LeetCodeSyncError elsewhere in this codebase.
    """


async def register_user(
    db: AsyncSession, first_name: str, last_name: str | None, email: str, password: str
) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise AuthError("An account with this email already exists.")

    user = User(
        name=f"{first_name} {last_name}".strip() if last_name else first_name,
        first_name=first_name,
        last_name=last_name,
        email=email,
        password_hash=hash_password(password),
        auth_provider="local",
        target_roles=[],
        target_companies=[],
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None or not user.password_hash:
        raise AuthError("Invalid email or password.")
    if not verify_password(password, user.password_hash):
        raise AuthError("Invalid email or password.")
    return user


async def authenticate_with_google(db: AsyncSession, credential: str) -> User:
    if not settings.google_client_id:
        raise AuthError("Google sign-in is not configured on this server.")

    try:
        idinfo = id_token.verify_oauth2_token(
            credential, google_requests.Request(), settings.google_client_id
        )
    except ValueError as e:
        raise AuthError(f"Invalid Google credential: {e}") from e

    google_id = idinfo["sub"]
    email = idinfo.get("email")
    first_name = idinfo.get("given_name", "") or "Polaris User"
    last_name = idinfo.get("family_name")
    avatar_url = idinfo.get("picture")

    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if user is None and email:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is not None:
            # Existing local account with a matching email — link Google
            # to it rather than creating a duplicate user.
            user.google_id = google_id
            user.avatar_url = user.avatar_url or avatar_url

    if user is None:
        user = User(
            name=f"{first_name} {last_name}".strip() if last_name else first_name,
            first_name=first_name,
            last_name=last_name,
            email=email,
            google_id=google_id,
            avatar_url=avatar_url,
            auth_provider="google",
            target_roles=[],
            target_companies=[],
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)
    return user


def build_token_response(user: User) -> dict:
    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "first_name": user.first_name or user.name,
            "last_name": user.last_name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "auth_provider": user.auth_provider,
        },
    }