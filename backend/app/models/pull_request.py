from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base

class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint("repository_id", "github_pr_id", name="uq_repo_pr"),
    )

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    github_pr_id = Column(BigInteger, nullable=False, index=True)
    pr_number = Column(Integer, nullable=False, index=True)
    title = Column(String(500), nullable=False, index=True)
    body = Column(Text, nullable=True)
    state = Column(String(20), nullable=False, index=True, default="open")  # open, closed, merged
    is_merged = Column(Boolean, default=False, nullable=False)
    merged_at = Column(DateTime(timezone=True), nullable=True)
    author = Column(String(100), nullable=True)
    labels = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)
    html_url = Column(String(500), nullable=False)
    diff_url = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    closed_at = Column(DateTime(timezone=True), nullable=True)

    repository = relationship("Repository", back_populates="pull_requests")
    commits = relationship(
        "Commit",
        back_populates="pull_request",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    code_diffs = relationship(
        "CodeDiff",
        back_populates="pull_request",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
