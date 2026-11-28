"""Sign-up, sign-in, and keeping a browser signed in.

Each sign-in answers with a short-lived access token, which the page sends as a
header, and sets the refresh token as a cookie. /auth/refresh trades that cookie
for a new pair; /auth/logout ends it.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.settings import settings
from app.models.facts import User
from app.schemas.auth import AuthResponse, GoogleAuthRequest, LoginRequest, RegisterRequest, UserResponse
from app.services.auth.auth_service import (
    AuthError,
    authenticate_user,
    authenticate_with_google,
    build_token_response,
    register_user,
    user_details,
)
from app.services.auth.sessions import end_session, renew_session, start_session

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

REFRESH_COOKIE = "polaris_refresh"
SESSION_ENDED = "Your session has ended. Sign in again."


def _cookie_options() -> dict:
    # Only sent to /auth, and never readable by a page's scripts.
    return {
        "path": "/auth", "httponly": True,
        "secure": settings.cookie_secure, "samesite": settings.cookie_samesite,
    }


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE, token, max_age=settings.refresh_token_days * 24 * 60 * 60, **_cookie_options(),
    )
    response.headers["Cache-Control"] = "no-store"


def require_own_page(request: Request) -> None:
    """The browser attaches the cookie by itself, so a request that another
    site makes it send is refused. Browsers say where such a request is from.
    """
    origin = request.headers.get("origin")
    if origin is not None and origin != settings.frontend_origin:
        raise HTTPException(status_code=403, detail="This request didn't come from the app.")


async def _signed_in(user: User, request: Request, response: Response, db) -> dict:
    previous = request.cookies.get(REFRESH_COOKIE)
    if previous:  # the browser is replacing that sign-in with this one
        await end_session(db, previous)
    _set_refresh_cookie(response, await start_session(db, user.id))
    return build_token_response(user)


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest, request: Request, response: Response, db=Depends(get_db)):
    try:
        user = await register_user(
            db, payload.first_name, payload.last_name, payload.email, payload.password
        )
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    logger.info("Registered new user (id=%s)", user.id)
    return await _signed_in(user, request, response, db)


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, request: Request, response: Response, db=Depends(get_db)):
    try:
        user = await authenticate_user(db, payload.email, payload.password)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    logger.info("Logged in user (id=%s)", user.id)
    return await _signed_in(user, request, response, db)


@router.post("/google", response_model=AuthResponse)
async def google_auth(payload: GoogleAuthRequest, request: Request, response: Response, db=Depends(get_db)):
    try:
        user = await authenticate_with_google(db, payload.credential)
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    logger.info("Google-authenticated user (id=%s)", user.id)
    return await _signed_in(user, request, response, db)


@router.post("/refresh", response_model=AuthResponse, dependencies=[Depends(require_own_page)])
async def refresh(request: Request, response: Response, db=Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    renewed = await renew_session(db, token) if token else None
    if renewed is None:
        refused = JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": SESSION_ENDED})
        refused.delete_cookie(REFRESH_COOKIE, **_cookie_options())
        return refused
    user, next_token = renewed
    _set_refresh_cookie(response, next_token)
    return build_token_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_own_page)])
async def logout(request: Request, response: Response, db=Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        await end_session(db, token)
    response.delete_cookie(REFRESH_COOKIE, **_cookie_options())


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return user_details(current_user)
