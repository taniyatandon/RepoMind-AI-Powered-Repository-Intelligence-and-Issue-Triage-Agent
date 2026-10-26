from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base

class ActionRecommendation(Base):
    __tablename__ = "action_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(
        Integer,
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type = Column(
        String(50),
        nullable=False,
    )  
    action_title = Column(String(200), nullable=False)
    rationale = Column(Text, nullable=False)
    severity = Column(String(20), default="info", nullable=False)  
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    issue = relationship("Issue", backref="recommendations")
