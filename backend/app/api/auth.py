"""Sign-up, sign-in, keeping a browser signed in, and the emailed links.

Each sign-in answers with a short-lived access token, which the page sends as a
header, and sets the refresh token as a cookie. /auth/refresh trades that cookie
for a new pair; /auth/logout ends it.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.settings import settings
from app.models.facts import User
from app.schemas.auth import (
    AuthResponse,
    EmailTokenRequest,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    Message,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
)
from app.services.auth import email_links
from app.services.auth.auth_service import (
    AuthError,
    authenticate_user,
    authenticate_with_google,
    build_token_response,
    register_user,
    user_details,
    users_with_email,
)
from app.services.auth.sessions import end_session, renew_session, start_session

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

REFRESH_COOKIE = "polaris_refresh"
SESSION_ENDED = "Your session has ended. Sign in again."
# The same whether or not there is such an account, so this can't be used to find out.
RESET_REQUESTED = "If there's an account for that address, we've sent it a link to set a new password."
BAD_LINK = "This link has expired or has already been used. Ask for a new one."
CONFIRMATION_SENT = "We've sent you a link. Check your inbox, and your spam folder."
ALREADY_CONFIRMED = "Your email address is already confirmed."
TOO_MANY_EMAILS = "We've sent several of these already. Check your spam folder, or try again in an hour."
EMAIL_FAILED = "The email couldn't be sent. Try again later."


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
async def register(
    payload: RegisterRequest, request: Request, response: Response, background: BackgroundTasks,
    db=Depends(get_db),
):
    try:
        user = await register_user(
            db, payload.first_name, payload.last_name, payload.email, payload.password
        )
    except AuthError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    logger.info("Registered new user (id=%s)", user.id)
    # After the reply: signing up doesn't wait for the mail service.
    background.add_task(email_links.send_confirmation, user.email, email_links.confirmation_token(user))
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


@router.post("/password/forgot", response_model=Message)
async def forgot_password(payload: ForgotPasswordRequest, background: BackgroundTasks, db=Depends(get_db)):
    for user in await users_with_email(db, payload.email):
        # Sent after the reply, which so takes no longer when there is an account.
        background.add_task(email_links.send_password_reset, user.email, email_links.reset_token(user))
    return Message(detail=RESET_REQUESTED)


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(payload: ResetPasswordRequest, db=Depends(get_db)):
    if not await email_links.reset_password(db, payload.token, payload.password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=BAD_LINK)


@router.post("/email/confirm", status_code=status.HTTP_204_NO_CONTENT)
async def confirm_email(payload: EmailTokenRequest, db=Depends(get_db)):
    if not await email_links.confirm_email(db, payload.token):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=BAD_LINK)


@router.post("/email/resend", response_model=Message)
async def resend_confirmation(current_user: User = Depends(get_current_user)):
    if current_user.email_verified_at is not None or not current_user.email:
        return Message(detail=ALREADY_CONFIRMED)
    # Waited for, so that the user hears if it couldn't be sent.
    sent = await email_links.send_confirmation(
        current_user.email, email_links.confirmation_token(current_user),
    )
    if sent == "limited":
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=TOO_MANY_EMAILS)
    if sent == "failed":
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=EMAIL_FAILED)
    return Message(detail=CONFIRMATION_SENT)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return user_details(current_user)
