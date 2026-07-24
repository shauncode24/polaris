from fastapi import FastAPI

from app.api.resume import router as resume_router

app = FastAPI(title="Polaris API")

app.include_router(resume_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}