from fastapi import FastAPI

from app.api.resume import router as resume_router
from app.api.sync import router as sync_router
from app.api.jobs import router as jobs_router

app = FastAPI(title="Polaris API")

app.include_router(resume_router)
app.include_router(sync_router)
app.include_router(jobs_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}