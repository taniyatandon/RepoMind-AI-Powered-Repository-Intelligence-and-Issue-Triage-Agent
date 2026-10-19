from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base

class CodeDiff(Base):
    __tablename__ = "code_diffs"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    pull_request_id = Column(
        Integer,
        ForeignKey("pull_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    commit_sha = Column(String(40), nullable=True, index=True)
    filename = Column(String(500), nullable=False)
    previous_filename = Column(String(500), nullable=True)
    status = Column(String(50), nullable=False, default="modified")  # added, modified, removed, renamed
    additions = Column(Integer, nullable=False, default=0)
    deletions = Column(Integer, nullable=False, default=0)
    changes_count = Column(Integer, nullable=False, default=0)
    diff_content = Column(Text, nullable=True)  # the patch / diff hunks
    raw_url = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    repository = relationship("Repository", back_populates="code_diffs")
    pull_request = relationship("PullRequest", back_populates="code_diffs")
