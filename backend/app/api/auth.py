from sqlalchemy.sql.functions import current_user
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.schemas.auth import AuthResponse, GoogleAuthRequest, LoginRequest, RegisterRequest, UserResponse
from app.services.auth.auth_service import (
    AuthError,
    authenticate_user,
    authenticate_with_google,
    build_token_response,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest, db=Depends(get_db)):
    try:
        user = await register_user(
            db, payload.first_name, payload.last_name, payload.email, payload.password
        )
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    print(f"[TRACING] Registered new user (id={user.id}, email={user.email})", flush=True)
    return build_token_response(user)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db=Depends(get_db)):
    try:
        user = await authenticate_user(db, payload.email, payload.password)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    print(f"[TRACING] Logged in user (id={user.id}, email={user.email})", flush=True)
    return build_token_response(user)


@router.post("/google", response_model=AuthResponse)
async def google_auth(payload: GoogleAuthRequest, db=Depends(get_db)):
    try:
        user = await authenticate_with_google(db, payload.credential)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    print(f"[TRACING] Google-authenticated user (id={user.id}, email={user.email})", flush=True)
    return build_token_response(user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
            id=str(current_user.id),
            first_name=current_user.first_name or current_user.name,
              last_name=current_user.last_name,
            email=current_user.email,
            avatar_url=current_user.avatar_url,
            auth_provider=current_user.auth_provider,
            github_username=current_user.github_username,
            leetcode_username=current_user.leetcode_username,
        )