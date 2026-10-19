from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ingestion_job import IngestionJob
from app.models.user import User
from app.schemas.ingestion_job import JobResponse
from app.security import get_current_user

router = APIRouter(prefix="/jobs", tags=["Ingestion Jobs"])

@router.get("/{job_id}", response_model=JobResponse)
def get_job_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion job with ID {job_id} not found",
        )
    return job
