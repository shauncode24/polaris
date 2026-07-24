from fastapi import APIRouter, UploadFile, Depends
from app.core.database import get_db
from app.services.ingestion import ingest_resume

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/upload")
async def upload_resume(file: UploadFile, db=Depends(get_db)):
    raw_bytes = await file.read()
    result = await ingest_resume(raw_bytes, db)
    return result