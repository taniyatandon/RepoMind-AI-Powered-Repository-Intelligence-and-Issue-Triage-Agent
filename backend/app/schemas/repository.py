from datetime import datetime
import re
from pydantic import BaseModel, ConfigDict, Field, field_validator

def parse_github_repo(input_str: str) -> tuple[str, str]:
    cleaned = input_str.strip()
    # Remove leading/trailing slashes
    cleaned = cleaned.rstrip("/")

    # If it's a URL or contains github.com
    url_pattern = r"(?:https?:\/\/)?(?:www\.)?github\.com\/([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)(?:\/.*)?"
    match = re.match(url_pattern, cleaned, re.IGNORECASE)
    if match:
        owner, repo = match.group(1), match.group(2)
        repo = repo.removesuffix(".git")
        return owner, repo

    # If format is "owner/repo"
    shorthand_pattern = r"^([a-zA-Z0-9_.-]+)\/([a-zA-Z0-9_.-]+)$"
    match = re.match(shorthand_pattern, cleaned)
    if match:
        owner, repo = match.group(1), match.group(2)
        repo = repo.removesuffix(".git")
        return owner, repo

    raise ValueError("Invalid repository format. Please provide 'owner/repo' or a valid GitHub repository URL.")

class RepoCreate(BaseModel):
    repo_url_or_name: str = Field(
        ...,
        description="GitHub repository in owner/repo format or full URL",
        min_length=3,
        max_length=500,
    )

    @field_validator("repo_url_or_name")
    @classmethod
    def validate_and_normalize(cls, v: str) -> str:
        owner, repo = parse_github_repo(v)
        return f"{owner}/{repo}"

class RepoResponse(BaseModel):
    id: int
    github_repo_id: int
    full_name: str
    name: str
    owner: str
    description: str | None = None
    html_url: str
    language: str | None = None
    stargazers_count: int = 0
    forks_count: int = 0
    open_issues_count: int = 0
    last_synced_at: datetime | None = None
    created_at: datetime
    stored_issues_count: int | None = None

    model_config = ConfigDict(from_attributes=True)

class RepoIngestAccepted(BaseModel):
    message: str
    job_id: int
    status: str
    repository_name: str
