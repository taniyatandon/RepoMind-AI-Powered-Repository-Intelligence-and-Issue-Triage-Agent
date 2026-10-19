import re
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.issue import Issue
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.schemas.search import (
    AIExplanationResponse,
    GlobalSearchResponse,
    SearchResultCodeChunk,
    SearchResultInvestigation,
    SearchResultIssue,
    SearchResultPullRequest,
    SearchResultRepository,
)
from app.security import get_current_user
from app.services.code_intelligence_service import CodeIntelligenceService

router = APIRouter(prefix="/search", tags=["Search"])
code_intel_service = CodeIntelligenceService()

class ExplainRequest(BaseModel):
    query: str
    repository_id: int | None = None

@router.get("", response_model=GlobalSearchResponse)
async def global_search(
    q: str = Query(..., min_length=1, max_length=150, description="Search query string"),
    mode: str = Query("all", description="Search mode: all, code, investigations, keyword"),
    repository_id: int | None = Query(None, description="Filter by repository ID"),
    limit: int = Query(5, ge=1, le=20, description="Maximum results per category"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clean_q = q.strip()
    if not clean_q:
        return GlobalSearchResponse(
            query=q,
            total=0,
            mode=mode,
            repositories=[],
            issues=[],
            pull_requests=[],
            code_chunks=[],
            investigations=[],
        )

    search_pattern = f"%{clean_q}%"
    num_match = re.match(r"^#?(\d+)$", clean_q)
    target_number = int(num_match.group(1)) if num_match else None

    repo_results: list[SearchResultRepository] = []
    issue_results: list[SearchResultIssue] = []
    pr_results: list[SearchResultPullRequest] = []
    code_results: list[SearchResultCodeChunk] = []
    investigation_results: list[SearchResultInvestigation] = []

    # 1. Repositories (Only if mode is 'all' or 'keyword', and not filtering to a specific repo)
    if mode in ("all", "keyword") and not repository_id:
        repo_matches = (
            db.query(Repository)
            .filter(
                or_(
                    Repository.full_name.ilike(search_pattern),
                    Repository.name.ilike(search_pattern),
                    Repository.owner.ilike(search_pattern),
                    Repository.description.ilike(search_pattern),
                )
            )
            .order_by(Repository.stargazers_count.desc(), Repository.id.desc())
            .limit(limit)
            .all()
        )
        repo_results = [
            SearchResultRepository(
                id=r.id,
                name=r.name,
                owner=r.owner,
                full_name=r.full_name,
                description=r.description,
                language=r.language,
                stargazers_count=r.stargazers_count,
                open_issues_count=r.open_issues_count,
            )
            for r in repo_matches
        ]

    # 2. Issues (if mode is 'all' or 'keyword')
    if mode in ("all", "keyword"):
        issue_query = db.query(Issue, Repository.full_name).join(
            Repository, Issue.repository_id == Repository.id
        )
        if repository_id:
            issue_query = issue_query.filter(Issue.repository_id == repository_id)

        if target_number is not None:
            issue_query = issue_query.filter(
                or_(
                    Issue.issue_number == target_number,
                    Issue.title.ilike(search_pattern),
                )
            )
        else:
            issue_query = issue_query.filter(
                or_(
                    Issue.title.ilike(search_pattern),
                    cast(Issue.labels, String).ilike(f'%"{clean_q}"%'),
                    Repository.full_name.ilike(search_pattern),
                )
            )

        issue_matches = (
            issue_query.order_by(Issue.created_at.desc(), Issue.id.desc())
            .limit(limit)
            .all()
        )
        issue_results = [
            SearchResultIssue(
                id=issue.id,
                repository_id=issue.repository_id,
                repository_name=repo_full_name,
                issue_number=issue.issue_number,
                title=issue.title,
                state=issue.state,
                comments_count=issue.comments_count,
                labels=issue.labels or [],
            )
            for issue, repo_full_name in issue_matches
        ]

    # 3. Pull Requests (if mode is 'all' or 'keyword')
    if mode in ("all", "keyword"):
        pr_query = db.query(PullRequest, Repository.full_name).join(
            Repository, PullRequest.repository_id == Repository.id
        )
        if repository_id:
            pr_query = pr_query.filter(PullRequest.repository_id == repository_id)

        if target_number is not None:
            pr_query = pr_query.filter(
                or_(
                    PullRequest.pr_number == target_number,
                    PullRequest.title.ilike(search_pattern),
                )
            )
        else:
            pr_query = pr_query.filter(
                or_(
                    PullRequest.title.ilike(search_pattern),
                    Repository.full_name.ilike(search_pattern),
                )
            )

        pr_matches = (
            pr_query.order_by(PullRequest.created_at.desc(), PullRequest.id.desc())
            .limit(limit)
            .all()
        )
        pr_results = [
            SearchResultPullRequest(
                id=pr.id,
                repository_id=pr.repository_id,
                repository_name=repo_full_name,
                pr_number=pr.pr_number,
                title=pr.title,
                state=pr.state,
                is_merged=pr.is_merged,
                author=pr.author,
                created_at=pr.created_at,
            )
            for pr, repo_full_name in pr_matches
        ]

    # 4. Semantic Code Search (if mode is 'all' or 'code')
    if mode in ("all", "code"):
        code_chunks_raw = await code_intel_service.search_code(
            db=db,
            query=clean_q,
            repository_id=repository_id,
            limit=limit,
        )
        code_results = [
            SearchResultCodeChunk(
                id=c["id"],
                repository_id=c["repository_id"],
                repository_name=c["repository_name"],
                file_path=c["file_path"],
                language=c["language"],
                start_line=c["start_line"],
                end_line=c["end_line"],
                content=c["content"],
                relevance_score=c["relevance_score"],
            )
            for c in code_chunks_raw
        ]

    # 5. Saved AI Investigations Search (if mode is 'all' or 'investigations')
    if mode in ("all", "investigations"):
        inv_raw = await code_intel_service.search_investigations(
            db=db,
            query=clean_q,
            repository_id=repository_id,
            limit=limit,
        )
        investigation_results = [
            SearchResultInvestigation(
                id=inv["id"],
                issue_id=inv["issue_id"],
                issue_number=inv["issue_number"],
                issue_title=inv["issue_title"],
                repository_id=inv["repository_id"],
                repository_name=inv["repository_name"],
                priority=inv["priority"],
                error_type=inv["error_type"],
                root_cause_hypothesis=inv["root_cause_hypothesis"],
                fix_target_file=inv["fix_target_file"],
                confidence=inv["confidence"],
                analyzed_at=inv["analyzed_at"],
            )
            for inv in inv_raw
        ]

    total_count = (
        len(repo_results)
        + len(issue_results)
        + len(pr_results)
        + len(code_results)
        + len(investigation_results)
    )

    return GlobalSearchResponse(
        query=q,
        total=total_count,
        mode=mode,
        repositories=repo_results,
        issues=issue_results,
        pull_requests=pr_results,
        code_chunks=code_results,
        investigations=investigation_results,
    )

@router.get("/code", response_model=list[SearchResultCodeChunk])
async def search_code_endpoint(
    q: str = Query(..., min_length=1, max_length=150, description="Natural language code query"),
    repository_id: int | None = Query(None, description="Optional repository ID filter"),
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw_results = await code_intel_service.search_code(
        db=db,
        query=q,
        repository_id=repository_id,
        limit=limit,
    )
    return [
        SearchResultCodeChunk(
            id=c["id"],
            repository_id=c["repository_id"],
            repository_name=c["repository_name"],
            file_path=c["file_path"],
            language=c["language"],
            start_line=c["start_line"],
            end_line=c["end_line"],
            content=c["content"],
            relevance_score=c["relevance_score"],
        )
        for c in raw_results
    ]

@router.get("/investigations", response_model=list[SearchResultInvestigation])
async def search_investigations_endpoint(
    q: str = Query(..., min_length=1, max_length=150, description="Search query for past diagnoses"),
    repository_id: int | None = Query(None, description="Optional repository ID filter"),
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw_results = await code_intel_service.search_investigations(
        db=db,
        query=q,
        repository_id=repository_id,
        limit=limit,
    )
    return [
        SearchResultInvestigation(
            id=inv["id"],
            issue_id=inv["issue_id"],
            issue_number=inv["issue_number"],
            issue_title=inv["issue_title"],
            repository_id=inv["repository_id"],
            repository_name=inv["repository_name"],
            priority=inv["priority"],
            error_type=inv["error_type"],
            root_cause_hypothesis=inv["root_cause_hypothesis"],
            fix_target_file=inv["fix_target_file"],
            confidence=inv["confidence"],
            analyzed_at=inv["analyzed_at"],
        )
        for inv in raw_results
    ]

@router.post("/explain", response_model=AIExplanationResponse)
async def explain_code_endpoint(
    body: ExplainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    explanation = await code_intel_service.explain_code(
        db=db,
        query=body.query,
        repository_id=body.repository_id,
    )
    return AIExplanationResponse.model_validate(explanation)
