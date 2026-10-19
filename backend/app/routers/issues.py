import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, cast
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.issue import Issue
from app.models.repository import Repository
from app.models.user import User
from app.schemas.issue import IssueResponse, PaginatedIssuesResponse
from app.security import get_current_user

router = APIRouter(tags=["Issues"])

@router.get("/repositories/{repo_id}/issues", response_model=PaginatedIssuesResponse)
def get_repository_issues(
    repo_id: int,
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status: open, closed, or all"),
    label: str | None = Query(None, description="Filter by label name"),
    title: str | None = Query(None, description="Search term for issue title"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify repository exists
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repo_id} not found",
        )

    query = db.query(Issue).filter(Issue.repository_id == repo_id)

    # 1. Status Filter
    if status_filter and status_filter.lower() != "all":
        query = query.filter(Issue.state == status_filter.lower())

    # 2. Title Filter (case-insensitive substring match)
    if title and title.strip():
        query = query.filter(Issue.title.ilike(f"%{title.strip()}%"))

    # 3. Label Filter
    if label and label.strip():
        # Universal JSON text match for both Postgres and SQLite
        clean_label = label.strip()
        query = query.filter(cast(Issue.labels, String).ilike(f'%"{clean_label}"%'))

    # Total count
    total = query.count()
    total_pages = math.ceil(total / per_page) if total > 0 else 1

    # Pagination & Ordering
    offset = (page - 1) * per_page
    issues = (
        query.order_by(Issue.created_at.desc(), Issue.issue_number.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    return PaginatedIssuesResponse(
        items=[IssueResponse.model_validate(i) for i in issues],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )

@router.get("/repositories/{repo_id}/labels", response_model=list[str])
def get_repository_labels(
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

    # Aggregate distinct labels from issues
    issues = db.query(Issue.labels).filter(Issue.repository_id == repo_id).all()
    label_names = set()
    for row in issues:
        raw_labels = row[0]
        if isinstance(raw_labels, list):
            for l in raw_labels:
                if isinstance(l, dict) and "name" in l:
                    label_names.add(l["name"])
                elif isinstance(l, str):
                    label_names.add(l)

    return sorted(list(label_names))

@router.get("/issues/{issue_id}", response_model=IssueResponse)
def get_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID {issue_id} not found",
        )
    return IssueResponse.model_validate(issue)

@router.get("/repositories/{repo_id}/issues/by-number/{issue_number}", response_model=IssueResponse)
def get_issue_by_number(
    repo_id: int,
    issue_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = (
        db.query(Issue)
        .filter(Issue.repository_id == repo_id, Issue.issue_number == issue_number)
        .first()
    )
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue #{issue_number} not found in repository",
        )
    return IssueResponse.model_validate(issue)
