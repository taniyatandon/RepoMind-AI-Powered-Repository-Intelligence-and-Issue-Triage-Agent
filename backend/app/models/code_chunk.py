from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.database import Base

class CodeChunk(Base):
    __tablename__ = "code_chunks"

    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_path = Column(String(500), nullable=False, index=True)
    language = Column(String(50), nullable=True, index=True)
    start_line = Column(Integer, nullable=False)
    end_line = Column(Integer, nullable=False)
    chunk_hash = Column(String(64), nullable=False, index=True)
    content = Column(Text, nullable=False)
    commit_sha = Column(String(40), nullable=True)
    embedding = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    indexed_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    repository = relationship("Repository", backref="code_chunks")
