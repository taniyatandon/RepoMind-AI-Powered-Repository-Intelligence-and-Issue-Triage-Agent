from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
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

class Issue(Base):
    __tablename__ = "issues"
    __table_args__ = (
        UniqueConstraint("repository_id", "github_issue_id", name="uq_repo_issue"),
    )

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    github_issue_id = Column(BigInteger, nullable=False, index=True)
    issue_number = Column(Integer, nullable=False, index=True)
    title = Column(String(500), nullable=False, index=True)
    body = Column(Text, nullable=True)
    state = Column(String(20), nullable=False, index=True, default="open")
    author = Column(String(100), nullable=True)
    labels = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list)
    comments_count = Column(Integer, default=0, nullable=False)
    html_url = Column(String(500), nullable=False)
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

    repository = relationship("Repository", back_populates="issues")
