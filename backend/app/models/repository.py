from datetime import datetime, timezone
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Repository(Base):
    __tablename__ = "repositories"

    id = Column(Integer, primary_key=True, index=True)
    github_repo_id = Column(BigInteger, unique=True, index=True, nullable=False)
    full_name = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    owner = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    html_url = Column(String(500), nullable=False)
    language = Column(String(100), nullable=True)
    stargazers_count = Column(Integer, default=0, nullable=False)
    forks_count = Column(Integer, default=0, nullable=False)
    open_issues_count = Column(Integer, default=0, nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    issues = relationship(
        "Issue",
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    ingestion_jobs = relationship("IngestionJob", back_populates="repository")
    pull_requests = relationship(
        "PullRequest",
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    commits = relationship(
        "Commit",
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    code_diffs = relationship(
        "CodeDiff",
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
