from datetime import datetime, timedelta, timezone

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.core.settings import settings

# bcrypt uses only the first 72 bytes of a password and refuses longer input,
# so longer passwords are cut here. Stored hashes were always made this way.
_BCRYPT_MAX_BYTES = 72

# Phase 1 §1.4 — encryption at rest for stored third-party credentials
# (currently: User.github_token). Fernet key is REQUIRED (settings.py
# fails fast if ENCRYPTION_KEY is unset), so this is safe to construct
# at import time.
_fernet = Fernet(settings.encryption_key.encode())


def _password_bytes(password: str) -> bytes:
    return password.encode()[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_password_bytes(plain_password), hashed_password.encode())
    except ValueError:  # the stored value isn't a bcrypt hash
        return False


# Marks a token as an access token. Tokens issued without it were valid for a
# week and are no longer accepted.
_ACCESS = "access"


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": user_id, "exp": expire, "use": _ACCESS}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """The user id in a valid, unexpired access token, or None."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
    return payload.get("sub") if payload.get("use") == _ACCESS else None


# --- Encryption at rest for sensitive third-party credentials ---------
# Never used for passwords (those stay one-way hashed with bcrypt
# above) — only for secrets we genuinely need to read back in plaintext
# to call an external API on the user's behalf (e.g. a GitHub PAT).

def encrypt_secret(plaintext: str | None) -> str | None:
    if not plaintext:
        return plaintext
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return ciphertext
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        # Defensive: a value written before encryption existed, or
        # corrupted/foreign data. Never raise into a request path over a
        # stored credential — treat it as absent so the caller falls
        # back to "no token on file" instead of crashing the request.
        return None