from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Commit(Base):
    __tablename__ = "commits"

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
        nullable=True,
        index=True,
    )
    sha = Column(String(40), nullable=False, index=True)
    message = Column(Text, nullable=False)
    author_name = Column(String(255), nullable=True)
    author_email = Column(String(255), nullable=True)
    committed_at = Column(DateTime(timezone=True), nullable=True)
    html_url = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    repository = relationship("Repository", back_populates="commits")
    pull_request = relationship("PullRequest", back_populates="commits")
