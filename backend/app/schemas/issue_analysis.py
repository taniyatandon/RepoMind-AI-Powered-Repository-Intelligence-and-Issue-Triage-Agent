from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict

class ActionRecommendationResponse(BaseModel):
    id: int
    issue_id: int
    action_type: str
    action_title: str
    rationale: str
    severity: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class IssueAnalysisResponse(BaseModel):
    id: int
    issue_id: int
    category: str
    priority: str
    confidence: float
    model_version: str
    root_cause_hypothesis: str | None = None
    error_type: str | None = None
    stack_trace_detected: bool = False
    reproduction_steps_detected: bool = False
    extracted_stack_trace: str | None = None
    affected_components: list[Any] = []
    
    # Proposed Code Fix & Solution fields
    fix_target_file: str | None = None
    proposed_code_patch: str | None = None
    verification_test_code: str | None = None
    patch_explanation: str | None = None

    analyzed_at: datetime
    recommendations: list[ActionRecommendationResponse] = []

    model_config = ConfigDict(from_attributes=True)
