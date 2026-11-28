from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.auth import router as auth_router
from app.api.background_jobs import router as background_jobs_router
from app.api.resume import router as resume_router
from app.api.sync import router as sync_router
from app.api.jobs import router as jobs_router
from app.api.job_intelligence import router as job_intelligence_router
from app.api.career import router as career_router
from app.api.interview import router as interview_router
from app.api.interview_kits import router as interview_kits_router
from app.api.profile import router as profile_router
from app.api.company_notes import router as company_notes_router
from app.api.projects import router as projects_router
from app.api.github import router as github_router
from app.api.identity import router as identity_router
from app.api.linkedin import router as linkedin_router
from app.api.tailored_resumes import router as tailored_resumes_router
from app.core.llm import LLMError
from app.core.logging_config import configure_logging
from app.core.rate_limit import RateLimitMiddleware
from app.core.settings import settings

configure_logging(level=settings.log_level)

app = FastAPI(title="Polaris API")


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Rejects requests whose declared Content-Length exceeds the limit, before
    any handler (and so any file parser) reads the body. Only the header is
    checked: a client that understates it isn't stopped here.
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


# The last one added is the outermost. CORS goes last so that refusals from the
# other two carry its headers (without them the browser can't read the message)
# and so that preflight requests aren't counted against the limits.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(MaxBodySizeMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # the name of a downloaded file
)

app.include_router(auth_router)
app.include_router(resume_router)
app.include_router(sync_router)
app.include_router(jobs_router)
app.include_router(job_intelligence_router)
app.include_router(career_router)
app.include_router(interview_router)
app.include_router(interview_kits_router)
app.include_router(profile_router)
app.include_router(company_notes_router)
app.include_router(projects_router)
app.include_router(github_router)
app.include_router(identity_router)
app.include_router(linkedin_router)
app.include_router(background_jobs_router)
app.include_router(tailored_resumes_router)


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, error: LLMError) -> JSONResponse:
    """AI features that have no fallback fail with a message the user can read."""
    return JSONResponse(status_code=error.status_code, content={"detail": str(error)})


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}