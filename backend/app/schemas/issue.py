from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict

class IssueResponse(BaseModel):
    id: int
    repository_id: int
    github_issue_id: int
    issue_number: int
    title: str
    body: str | None = None
    state: str
    author: str | None = None
    labels: list[Any] = []
    comments_count: int = 0
    html_url: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

class PaginatedIssuesResponse(BaseModel):
    items: list[IssueResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
