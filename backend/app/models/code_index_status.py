from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base

class CodeIndexStatus(Base):
    __tablename__ = "code_index_statuses"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status = Column(
        String(30),
        default="not_indexed",
        nullable=False,
        index=True,
    )  # not_indexed, indexing, indexed, partially_indexed, failed
    total_files = Column(Integer, default=0, nullable=False)
    indexed_chunks = Column(Integer, default=0, nullable=False)
    commit_sha = Column(String(40), nullable=True)
    last_indexed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    repository = relationship("Repository", backref="index_status")
