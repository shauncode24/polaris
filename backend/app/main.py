# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.resume import router as resume_router
from app.api.sync import router as sync_router
from app.api.jobs import router as jobs_router
from app.api.career import router as career_router
from app.api.interview import router as interview_router
from app.api.profile import router as profile_router
from app.api.company_notes import router as company_notes_router
from app.core.settings import settings

app = FastAPI(title="Polaris API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(resume_router)
app.include_router(sync_router)
app.include_router(jobs_router)
app.include_router(career_router)
app.include_router(interview_router)
app.include_router(profile_router)
app.include_router(company_notes_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}