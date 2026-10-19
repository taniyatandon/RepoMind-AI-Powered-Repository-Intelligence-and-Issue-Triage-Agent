from datetime import datetime
from pydantic import BaseModel, ConfigDict

class JobResponse(BaseModel):
    id: int
    repository_id: int | None = None
    repository_name: str
    status: str
    total_issues_ingested: int = 0
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)
