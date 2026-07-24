from fastapi import APIRouter, HTTPException, UploadFile, Depends
from app.core.database import get_db
from app.services.resume.ingestion import ingest_resume
from app.services.resume.reviewer import generate_resume_review
from app.services.user_helpers import get_or_create_default_user

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/upload")
async def upload_resume(file: UploadFile, db=Depends(get_db)):
    print(f"[TRACING] Received upload request for file: {file.filename}", flush=True)
    raw_bytes = await file.read()
    print(f"[TRACING] Read {len(raw_bytes)} bytes from file.", flush=True)
    result = await ingest_resume(raw_bytes, db, filename=file.filename)
    print(f"[TRACING] Ingestion pipeline finished successfully.", flush=True)
    return result


@router.post("/review")
async def review_resume(db=Depends(get_db)):
    print("[TRACING] Received resume review request.", flush=True)
    user = await get_or_create_default_user(db)
    try:
        report = await generate_resume_review(db, user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    print("[TRACING] Resume review generated successfully.", flush=True)
    return report