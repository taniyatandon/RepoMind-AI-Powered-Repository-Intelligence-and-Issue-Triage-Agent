from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

class SearchResultRepository(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: Literal["repository"] = "repository"
    name: str
    owner: str
    full_name: str
    description: str | None = None
    language: str | None = None
    stargazers_count: int = 0
    open_issues_count: int = 0

class SearchResultIssue(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: Literal["issue"] = "issue"
    repository_id: int
    repository_name: str
    issue_number: int
    title: str
    state: str
    comments_count: int = 0
    labels: list[Any] = Field(default_factory=list)

class SearchResultPullRequest(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: Literal["pull_request"] = "pull_request"
    repository_id: int
    repository_name: str
    pr_number: int
    title: str
    state: str
    is_merged: bool = False
    author: str | None = None
    created_at: datetime | None = None

class SearchResultCodeChunk(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: Literal["code_chunk"] = "code_chunk"
    repository_id: int
    repository_name: str
    file_path: str
    language: str = "text"
    start_line: int
    end_line: int
    content: str
    relevance_score: float = 0.0

class SearchResultInvestigation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: Literal["investigation"] = "investigation"
    issue_id: int
    issue_number: int
    issue_title: str
    repository_id: int
    repository_name: str
    priority: str
    error_type: str
    root_cause_hypothesis: str | None = None
    fix_target_file: str | None = None
    confidence: float = 0.85
    analyzed_at: str | None = None

class CodeCitation(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    language: str
    repository_name: str
    snippet: str

class AIExplanationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query: str
    answer: str
    evidence_sufficient: bool
    citations: list[CodeCitation] = Field(default_factory=list)
    supporting_chunks: list[SearchResultCodeChunk] = Field(default_factory=list)

class CodeIndexStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    repository_id: int
    status: str
    total_files: int = 0
    indexed_chunks: int = 0
    commit_sha: str | None = None
    last_indexed_at: datetime | None = None
    error_message: str | None = None

class GlobalSearchResponse(BaseModel):
    query: str
    total: int
    mode: str = "all"  # "all", "code", "investigations", "keyword"
    repositories: list[SearchResultRepository] = Field(default_factory=list)
    issues: list[SearchResultIssue] = Field(default_factory=list)
    pull_requests: list[SearchResultPullRequest] = Field(default_factory=list)
    code_chunks: list[SearchResultCodeChunk] = Field(default_factory=list)
    investigations: list[SearchResultInvestigation] = Field(default_factory=list)
