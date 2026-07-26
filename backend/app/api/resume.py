from fastapi import APIRouter, HTTPException, UploadFile, Depends
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.facts import User
from app.services.resume.ingestion import ingest_resume
from app.services.resume.reviewer import generate_resume_review

router = APIRouter(prefix="/resume", tags=["resume"])


@router.post("/upload")
async def upload_resume(file: UploadFile, current_user: User = Depends(get_current_user), db=Depends(get_db)):
    raw_bytes = await file.read()
    result = await ingest_resume(raw_bytes, db, current_user, filename=file.filename)
    return result


@router.post("/review")
async def review_resume(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    try:
        report = await generate_resume_review(db, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return report