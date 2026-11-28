from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr


def _long_enough(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    return password


NewPassword = Annotated[str, AfterValidator(_long_enough)]


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str | None = None
    email: EmailStr
    password: NewPassword


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str  # ID token from Google Identity Services


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class EmailTokenRequest(BaseModel):
    token: str


class ResetPasswordRequest(EmailTokenRequest):
    password: NewPassword


class Message(BaseModel):
    detail: str


class UserResponse(BaseModel):
    id: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None
    auth_provider: str
    github_username: str | None = None
    leetcode_username: str | None = None
    # True while AI features wait for the user to confirm their address.
    needs_email_confirmation: bool


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse