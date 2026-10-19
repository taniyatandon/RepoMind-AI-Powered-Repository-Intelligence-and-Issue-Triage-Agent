from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base

class IssueAnalysis(Base):
    __tablename__ = "issue_analyses"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(
        Integer,
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    category = Column(String(50), nullable=False, index=True)  # bug, feature_request, improvement, question, documentation
    priority = Column(String(20), nullable=False, index=True)  # P0_CRITICAL, P1_HIGH, P2_MEDIUM, P3_LOW
    confidence = Column(Float, nullable=False, default=0.85)
    model_version = Column(String(50), nullable=False, default="repomind-triage-v1.0")
    
    # Debugging & Diagnosis fields
    root_cause_hypothesis = Column(Text, nullable=True)
    error_type = Column(String(100), nullable=True)
    stack_trace_detected = Column(Boolean, default=False, nullable=False)
    reproduction_steps_detected = Column(Boolean, default=False, nullable=False)
    extracted_stack_trace = Column(Text, nullable=True)
    affected_components = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=list,
    )

    # Code Fix & Solution fields
    fix_target_file = Column(String(255), nullable=True)
    proposed_code_patch = Column(Text, nullable=True)
    verification_test_code = Column(Text, nullable=True)
    patch_explanation = Column(Text, nullable=True)

    analyzed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    issue = relationship("Issue", backref="analysis")
