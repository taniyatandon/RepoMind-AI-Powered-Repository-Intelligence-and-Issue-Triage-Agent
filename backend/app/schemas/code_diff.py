from datetime import datetime
from pydantic import BaseModel, ConfigDict

class CommitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    pull_request_id: int | None = None
    sha: str
    message: str
    author_name: str | None = None
    author_email: str | None = None
    committed_at: datetime | None = None
    html_url: str | None = None
    created_at: datetime

class CodeDiffResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    repository_id: int
    pull_request_id: int
    commit_sha: str | None = None
    filename: str
    previous_filename: str | None = None
    status: str
    additions: int = 0
    deletions: int = 0
    changes_count: int = 0
    diff_content: str | None = None
    raw_url: str | None = None
    created_at: datetime

class ResolvedIssueSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_number: int
    title: str
    state: str
    html_url: str

class PullRequestChangesResponse(BaseModel):
    pr_id: int
    pr_number: int
    total_commits: int
    total_files_changed: int
    total_additions: int
    total_deletions: int
    resolved_issues: list[ResolvedIssueSummary] = []
    commits: list[CommitResponse]
    files: list[CodeDiffResponse]
