from fastapi import APIRouter, UploadFile, Depends
from app.core.database import get_db
from app.services.resume.ingestion import ingest_resume

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/upload")
async def upload_resume(file: UploadFile, db=Depends(get_db)):
    print(f"[TRACING] Received upload request for file: {file.filename}", flush=True)
    raw_bytes = await file.read()
    print(f"[TRACING] Read {len(raw_bytes)} bytes from file.", flush=True)
    result = await ingest_resume(raw_bytes, db)
    print(f"[TRACING] Ingestion pipeline finished successfully.", flush=True)
    return result