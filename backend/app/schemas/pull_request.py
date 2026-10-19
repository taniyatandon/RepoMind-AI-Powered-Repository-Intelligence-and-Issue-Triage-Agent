from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict

class PullRequestResponse(BaseModel):
    id: int
    repository_id: int
    github_pr_id: int
    pr_number: int
    title: str
    body: str | None = None
    state: str
    is_merged: bool = False
    merged_at: datetime | None = None
    author: str | None = None
    labels: list[Any] = []
    html_url: str
    diff_url: str | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

class PaginatedPullRequestsResponse(BaseModel):
    items: list[PullRequestResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
