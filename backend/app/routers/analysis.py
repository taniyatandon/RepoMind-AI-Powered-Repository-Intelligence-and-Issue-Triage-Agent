from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.action_recommendation import ActionRecommendation
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
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
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
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID {issue_id} not found",
        )

    analysis = (
        db.query(IssueAnalysis).filter(IssueAnalysis.issue_id == issue.id).first()
    )

    if not analysis:
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
    repo = db.query(Repository).filter(Repository.id == repo_id).first()
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID {repo_id} not found",
        )

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
