import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.auth import router as auth_router
from app.api.resume import router as resume_router
from app.api.sync import router as sync_router
from app.api.jobs import router as jobs_router
from app.api.job_intelligence import router as job_intelligence_router
from app.api.career import router as career_router
from app.api.interview import router as interview_router
from app.api.profile import router as profile_router
from app.api.company_notes import router as company_notes_router
from app.api.projects import router as projects_router
from app.api.github import router as github_router
from app.api.identity import router as identity_router
from app.api.linkedin import router as linkedin_router
from app.core.logging_config import configure_logging
from app.core.settings import settings

configure_logging(level=settings.log_level)

app = FastAPI(title="Polaris API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Phase 1 security baseline (§1.4) — rejects requests whose
    declared Content-Length exceeds a configured ceiling before any
    handler (and therefore any file-parsing library) ever touches the
    body. This is a coarse, header-based check — it does not protect
    against a client lying about Content-Length and streaming more
    anyway, but it stops the common case cheaply and is a real
    improvement over no limit at all.
    """

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > settings.max_request_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body exceeds the maximum allowed size."},
                    )
            except ValueError:
                pass
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Minimal in-memory sliding-window rate limiter — Phase 1 security
    baseline (§1.4). Deliberately simple (per-process, per-client-IP, no
    external store): nothing in this codebase describes a distributed/
    multi-process deployment, so a Redis-backed limiter would be
    speculative infrastructure not grounded in anything actually here.
    This is enough to blunt basic abuse (a runaway client, a scripted
    loop) without adding a new external dependency.
    """

    def __init__(self, app, max_requests: int, window_seconds: int):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        hits = self._hits[client_ip]

        while hits and now - hits[0] > self.window_seconds:
            hits.popleft()

        if len(hits) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down and try again shortly."},
            )

        hits.append(now)
        return await call_next(request)


app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
)
app.add_middleware(MaxBodySizeMiddleware)

app.include_router(auth_router)
app.include_router(resume_router)
app.include_router(sync_router)
app.include_router(jobs_router)
app.include_router(job_intelligence_router)
app.include_router(career_router)
app.include_router(interview_router)
app.include_router(profile_router)
app.include_router(company_notes_router)
app.include_router(projects_router)
app.include_router(github_router)
app.include_router(identity_router)
app.include_router(linkedin_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}