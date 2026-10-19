import math
import re
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.commit import Commit
from app.models.code_diff import CodeDiff
from app.models.issue import Issue
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.schemas.code_diff import (
    CodeDiffResponse,
    CommitResponse,
    PullRequestChangesResponse,
    ResolvedIssueSummary,
)
from app.schemas.pull_request import PaginatedPullRequestsResponse, PullRequestResponse
from app.security import get_current_user
from app.services.ingestion_service import IngestionService

router = APIRouter(tags=["Pull Requests"])

def extract_resolved_issues(db: Session, pr: PullRequest, commits: list[Commit]) -> list[ResolvedIssueSummary]:
    texts = [pr.title or "", pr.body or ""]
    for c in commits:
        if c.message:
            texts.append(c.message)
    combined = " ".join(texts)

    pattern = r"(?:fix(?:es|ed)?|close[sd]?|resolve[sd]?)\s+#(\d+)"
    raw_nums = re.findall(pattern, combined, re.IGNORECASE)

    if not raw_nums and pr.title:
        raw_nums.extend(re.findall(r"#(\d+)", pr.title))

    issue_numbers = []
    for num_str in raw_nums:
        try:
            n = int(num_str)
            if n not in issue_numbers and n != pr.pr_number:
                issue_numbers.append(n)
        except ValueError:
            pass

    resolved_summaries: list[ResolvedIssueSummary] = []
    if issue_numbers:
        matching_issues = (
            db.query(Issue)
            .filter(
                Issue.repository_id == pr.repository_id,
                Issue.issue_number.in_(issue_numbers),
            )
            .all()
        )
        found_nums = set()
        for iss in matching_issues:
            found_nums.add(iss.issue_number)
            resolved_summaries.append(
                ResolvedIssueSummary(
                    id=iss.id,
                    issue_number=iss.issue_number,
                    title=iss.title,
                    state=iss.state,
                    html_url=iss.html_url,
                )
            )

        repo_url = pr.repository.html_url if pr.repository else "https://github.com"
        for n in issue_numbers:
            if n not in found_nums:
                resolved_summaries.append(
                    ResolvedIssueSummary(
                        id=0,
                        issue_number=n,
                        title=f"GitHub Issue #{n}",
                        state="referenced",
                        html_url=f"{repo_url}/issues/{n}",
                    )
                )

    return resolved_summaries

@router.get("/repositories/{repo_id}/pulls", response_model=PaginatedPullRequestsResponse)
def get_repository_pull_requests(
    repo_id: int,
    page: int = Query(1, ge=1, description="Page number starting from 1"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status: open, closed, merged, or all"),
    title: str | None = Query(None, description="Search term for PR title"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repo_id} not found",
        )

    query = db.query(PullRequest).filter(PullRequest.repository_id == repo_id)

    # Status filter
    if status_filter and status_filter.lower() != "all":
        st = status_filter.lower()
        if st == "merged":
            query = query.filter(PullRequest.is_merged.is_(True))
        elif st == "closed":
            query = query.filter(PullRequest.state == "closed", PullRequest.is_merged.is_(False))
        elif st == "open":
            query = query.filter(PullRequest.state == "open")

    # Title filter
    if title and title.strip():
        query = query.filter(PullRequest.title.ilike(f"%{title.strip()}%"))

    total = query.count()
    total_pages = math.ceil(total / per_page) if total > 0 else 1

    offset = (page - 1) * per_page
    prs = (
        query.order_by(PullRequest.created_at.desc(), PullRequest.pr_number.desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    return PaginatedPullRequestsResponse(
        items=[PullRequestResponse.model_validate(p) for p in prs],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )

@router.get("/pulls/{pr_id}", response_model=PullRequestResponse)
def get_pull_request(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull Request with ID {pr_id} not found",
        )
    return PullRequestResponse.model_validate(pr)

@router.get("/pulls/{pr_id}/commits", response_model=list[CommitResponse])
def get_pull_request_commits(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull Request with ID {pr_id} not found",
        )
    commits = (
        db.query(Commit)
        .filter(Commit.pull_request_id == pr_id)
        .order_by(Commit.committed_at.asc(), Commit.id.asc())
        .all()
    )
    return [CommitResponse.model_validate(c) for c in commits]

@router.get("/pulls/{pr_id}/diffs", response_model=list[CodeDiffResponse])
def get_pull_request_diffs(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull Request with ID {pr_id} not found",
        )
    diffs = (
        db.query(CodeDiff)
        .filter(CodeDiff.pull_request_id == pr_id)
        .order_by(CodeDiff.filename.asc())
        .all()
    )
    return [CodeDiffResponse.model_validate(d) for d in diffs]

@router.get("/pulls/{pr_id}/changes", response_model=PullRequestChangesResponse)
async def get_pull_request_changes(
    pr_id: int,
    auto_sync: bool = Query(True, description="Fetch from GitHub if not yet cached"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull Request with ID {pr_id} not found",
        )

    commits = (
        db.query(Commit)
        .filter(Commit.pull_request_id == pr_id)
        .order_by(Commit.committed_at.asc(), Commit.id.asc())
        .all()
    )
    diffs = (
        db.query(CodeDiff)
        .filter(CodeDiff.pull_request_id == pr_id)
        .order_by(CodeDiff.filename.asc())
        .all()
    )

    if (len(commits) == 0 or len(diffs) == 0) and auto_sync and pr.repository:
        try:
            ingestion_service = IngestionService()
            await ingestion_service.ingest_pull_request_diffs(db, pr.repository, pr)
            commits = (
                db.query(Commit)
                .filter(Commit.pull_request_id == pr_id)
                .order_by(Commit.committed_at.asc(), Commit.id.asc())
                .all()
            )
            diffs = (
                db.query(CodeDiff)
                .filter(CodeDiff.pull_request_id == pr_id)
                .order_by(CodeDiff.filename.asc())
                .all()
            )
        except Exception:
            pass

    total_additions = sum(d.additions for d in diffs)
    total_deletions = sum(d.deletions for d in diffs)
    resolved_issues = extract_resolved_issues(db, pr, commits)

    return PullRequestChangesResponse(
        pr_id=pr.id,
        pr_number=pr.pr_number,
        total_commits=len(commits),
        total_files_changed=len(diffs),
        total_additions=total_additions,
        total_deletions=total_deletions,
        resolved_issues=resolved_issues,
        commits=[CommitResponse.model_validate(c) for c in commits],
        files=[CodeDiffResponse.model_validate(d) for d in diffs],
    )

@router.post("/pulls/{pr_id}/sync-diffs", response_model=PullRequestChangesResponse)
async def sync_pull_request_diffs(
    pr_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pr = db.query(PullRequest).filter(PullRequest.id == pr_id).first()
    if not pr:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pull Request with ID {pr_id} not found",
        )
    if not pr.repository:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository associated with PR not found",
        )

    ingestion_service = IngestionService()
    await ingestion_service.ingest_pull_request_diffs(db, pr.repository, pr)

    commits = (
        db.query(Commit)
        .filter(Commit.pull_request_id == pr_id)
        .order_by(Commit.committed_at.asc(), Commit.id.asc())
        .all()
    )
    diffs = (
        db.query(CodeDiff)
        .filter(CodeDiff.pull_request_id == pr_id)
        .order_by(CodeDiff.filename.asc())
        .all()
    )

    total_additions = sum(d.additions for d in diffs)
    total_deletions = sum(d.deletions for d in diffs)
    resolved_issues = extract_resolved_issues(db, pr, commits)

    return PullRequestChangesResponse(
        pr_id=pr.id,
        pr_number=pr.pr_number,
        total_commits=len(commits),
        total_files_changed=len(diffs),
        total_additions=total_additions,
        total_deletions=total_deletions,
        resolved_issues=resolved_issues,
        commits=[CommitResponse.model_validate(c) for c in commits],
        files=[CodeDiffResponse.model_validate(d) for d in diffs],
    )
