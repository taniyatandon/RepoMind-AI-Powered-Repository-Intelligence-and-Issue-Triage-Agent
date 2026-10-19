from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ingestion_job import IngestionJob
from app.models.issue import Issue
from app.models.repository import Repository
from app.models.user import User
from app.schemas.repository import RepoCreate, RepoIngestAccepted, RepoResponse
from app.schemas.search import CodeIndexStatusResponse
from app.security import get_current_user
from app.services.code_indexing_service import CodeIndexingService
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/repositories", tags=["Repositories"])

@router.post("", response_model=RepoIngestAccepted, status_code=status.HTTP_202_ACCEPTED)
def add_repository(
    repo_in: RepoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized_name = repo_in.repo_url_or_name

    # Check for existing repository
    existing_repo = (
        db.query(Repository)
        .filter(Repository.full_name == normalized_name)
        .first()
    )
    if existing_repo:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Repository '{normalized_name}' is already added.",
        )

    # Check for already running / pending job
    active_job = (
        db.query(IngestionJob)
        .filter(
            IngestionJob.repository_name == normalized_name,
            IngestionJob.status.in_(["pending", "running"]),
        )
        .first()
    )
    if active_job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An ingestion job is already active for '{normalized_name}'.",
        )

    # Create ingestion job in pending status
    job = IngestionJob(
        repository_name=normalized_name,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Launch background task
    ingestion_service = IngestionService()
    background_tasks.add_task(ingestion_service.run_ingestion_job, job.id)

    return RepoIngestAccepted(
        message=f"Ingestion job for '{normalized_name}' created.",
        job_id=job.id,
        status="pending",
        repository_name=normalized_name,
    )

@router.get("", response_model=list[RepoResponse])
def list_repositories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
    results = []
    for repo in repos:
        stored_count = db.query(Issue).filter(Issue.repository_id == repo.id).count()
        repo_data = RepoResponse.model_validate(repo)
        repo_data.stored_issues_count = stored_count
        results.append(repo_data)
    return results

@router.get("/{repo_id}", response_model=RepoResponse)
def get_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repo_id} not found",
        )
    stored_count = db.query(Issue).filter(Issue.repository_id == repo.id).count()
    repo_data = RepoResponse.model_validate(repo)
    repo_data.stored_issues_count = stored_count
    return repo_data

@router.delete("/{repo_id}", status_code=status.HTTP_200_OK)
def delete_repository(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repo_id} not found",
        )
    # Dissociate any jobs pointing to this repository to retain job history as per PRD Section 6.4
    db.query(IngestionJob).filter(IngestionJob.repository_id == repo.id).update(
        {"repository_id": None}
    )
    db.delete(repo)
    db.commit()
    return {"message": f"Repository '{repo.full_name}' deleted successfully."}

@router.post("/{repo_id}/sync", response_model=RepoIngestAccepted, status_code=status.HTTP_202_ACCEPTED)
def sync_repository(
    repo_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repo_id} not found",
        )

    # Check for active job
    active_job = (
        db.query(IngestionJob)
        .filter(
            IngestionJob.repository_name == repo.full_name,
            IngestionJob.status.in_(["pending", "running"]),
        )
        .first()
    )
    if active_job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A sync job is already active for '{repo.full_name}'.",
        )

    job = IngestionJob(
        repository_id=repo.id,
        repository_name=repo.full_name,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    ingestion_service = IngestionService()
    background_tasks.add_task(ingestion_service.run_ingestion_job, job.id)

    return RepoIngestAccepted(
        message=f"Sync job for '{repo.full_name}' started.",
        job_id=job.id,
        status="pending",
        repository_name=repo.full_name,
    )

@router.get("/{repo_id}/indexing-status", response_model=CodeIndexStatusResponse)
def get_indexing_status(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repo_id} not found",
        )
    indexing_service = CodeIndexingService()
    status_rec = indexing_service.get_or_create_status(db, repo.id)
    return CodeIndexStatusResponse.model_validate(status_rec)

@router.post("/{repo_id}/index-code", response_model=CodeIndexStatusResponse)
async def index_repository_code(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repo_id} not found",
        )
    indexing_service = CodeIndexingService()
    result_status = await indexing_service.index_repository_code(db, repo)
    return CodeIndexStatusResponse.model_validate(result_status)
