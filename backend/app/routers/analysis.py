from datetime import timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.authorization import get_owned_repository
from app.models.action_recommendation import ActionRecommendation
from app.models.code_index_status import CodeIndexStatus
from app.models.issue import Issue
from app.models.issue_analysis import IssueAnalysis
from app.models.repository import Repository
from app.models.user import User
from app.schemas.issue_analysis import (
    ActionRecommendationResponse,
    IssueAnalysisResponse,
)
from app.security import get_current_user
from app.services.triage_service import TriageService

router = APIRouter(tags=["Issue Intelligence & Debugging"])

@router.post("/issues/{issue_id}/diagnose", response_model=IssueAnalysisResponse)
def diagnose_single_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = db.query(Issue).join(Repository).filter(
        Issue.id == issue_id, Repository.user_id == current_user.id
    ).first()
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID {issue_id} not found",
        )

    triage_service = TriageService()
    analysis = triage_service.diagnose_issue(issue, db)

    recs = (
        db.query(ActionRecommendation)
        .filter(ActionRecommendation.issue_id == issue.id)
        .order_by(ActionRecommendation.id.asc())
        .all()
    )

    resp = IssueAnalysisResponse.model_validate(analysis)
    resp.recommendations = [ActionRecommendationResponse.model_validate(r) for r in recs]
    return resp

@router.get("/issues/{issue_id}/analysis", response_model=IssueAnalysisResponse)
def get_issue_analysis(
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    issue = db.query(Issue).join(Repository).filter(
        Issue.id == issue_id, Repository.user_id == current_user.id
    ).first()
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID {issue_id} not found",
        )

    analysis = (
        db.query(IssueAnalysis).filter(IssueAnalysis.issue_id == issue.id).first()
    )

    index_status = db.query(CodeIndexStatus).filter(
        CodeIndexStatus.repository_id == issue.repository_id
    ).first()
    current_index_state = index_status.status if index_status else "not_indexed"

    def normalized_timestamp(value):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    index_changed = bool(analysis) and (
        analysis.repository_index_status != current_index_state
        or normalized_timestamp(analysis.repository_indexed_at)
        != normalized_timestamp(index_status.last_indexed_at if index_status else None)
    )
    content_changed = bool(analysis) and (
        analysis.source_content_digest
        != TriageService.issue_content_digest(issue.title, issue.body)
    )
    if (
        not analysis
        or analysis.model_version != TriageService.MODEL_VERSION
        or index_changed
        or content_changed
    ):
        # Run diagnosis on demand if not yet analyzed
        triage_service = TriageService()
        analysis = triage_service.diagnose_issue(issue, db)

    recs = (
        db.query(ActionRecommendation)
        .filter(ActionRecommendation.issue_id == issue.id)
        .order_by(ActionRecommendation.id.asc())
        .all()
    )

    resp = IssueAnalysisResponse.model_validate(analysis)
    resp.recommendations = [ActionRecommendationResponse.model_validate(r) for r in recs]
    return resp

@router.post("/repositories/{repo_id}/triage-all")
def triage_all_repository_issues(
    repo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = get_owned_repository(db, repo_id, current_user.id)

    issues = db.query(Issue).filter(Issue.repository_id == repo_id).all()
    triage_service = TriageService()

    count = 0
    for issue in issues:
        triage_service.diagnose_issue(issue, db)
        count += 1

    return {
        "message": f"Successfully analyzed and triaged {count} issues for repository '{repo.full_name}'",
        "total_analyzed": count,
    }
