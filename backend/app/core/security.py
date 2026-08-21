from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Phase 1 §1.4 — encryption at rest for stored third-party credentials
# (currently: User.github_token). Fernet key is REQUIRED (settings.py
# fails fast if ENCRYPTION_KEY is unset), so this is safe to construct
# at import time.
_fernet = Fernet(settings.encryption_key.encode())


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


# --- Encryption at rest for sensitive third-party credentials ---------
# Never used for passwords (those stay one-way hashed via passlib
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