from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.repository import Repository


def get_owned_repository(db: Session, repo_id: int, user_id: int) -> Repository:
    repository = (
        db.query(Repository)
        .filter(Repository.id == repo_id, Repository.user_id == user_id)
        .first()
    )
    if not repository:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repo_id} not found",
        )
    return repository
