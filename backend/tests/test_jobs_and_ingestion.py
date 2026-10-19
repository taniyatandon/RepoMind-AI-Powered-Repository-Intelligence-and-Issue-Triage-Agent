from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from app.models.ingestion_job import IngestionJob
from app.models.issue import Issue
from app.models.repository import Repository
from app.services.github_client import (
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from app.services.ingestion_service import IngestionService

def test_get_ingestion_job_status(client, auth_headers, db_session):
    job = IngestionJob(
        repository_name="psf/black",
        status="running",
    )
    db_session.add(job)
    db_session.commit()

    res = client.get(f"/api/jobs/{job.id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == job.id
    assert data["status"] == "running"
    assert data["repository_name"] == "psf/black"

def test_get_ingestion_job_not_found(client, auth_headers):
    res = client.get("/api/jobs/99999", headers=auth_headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()

def test_github_client_headers_and_url():
    client_default = GitHubClient()
    assert "User-Agent" in client_default.headers
    assert "application/vnd.github.v3+json" in client_default.headers["Accept"]

    client_with_token = GitHubClient(token="ghp_testtoken123")
    assert client_with_token.headers["Authorization"] == "Bearer ghp_testtoken123"

@pytest.mark.asyncio
async def test_github_client_handles_rate_limit_error():
    client = GitHubClient()
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 403
    mock_response.headers = {"x-ratelimit-remaining": "0"}
    mock_response.text = "API rate limit exceeded for user"
    mock_response.is_error = True

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
        with pytest.raises(GitHubRateLimitError) as exc_info:
            await client.get_repository("owner", "repo")
        assert "rate limit exceeded" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_github_client_handles_not_found_error():
    client = GitHubClient()
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.headers = {}
    mock_response.text = '{"message": "Not Found"}'
    mock_response.is_error = True

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
        with pytest.raises(GitHubNotFoundError) as exc_info:
            await client.get_repository("nonexistent", "repo")
        assert "not found" in str(exc_info.value).lower()

@pytest.mark.asyncio
async def test_github_client_filters_pull_requests():
    client = GitHubClient()
    # GitHub issues API returns items where PRs have 'pull_request' key
    api_items = [
        {"id": 1, "number": 10, "title": "Actual Issue", "body": "Issue text", "labels": []},
        {"id": 2, "number": 11, "title": "Pull Request Title", "body": "PR text", "pull_request": {}, "labels": []},
        {"id": 3, "number": 12, "title": "Second Issue", "body": "Second issue text", "labels": []},
    ]

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.is_error = False
    mock_response.json.return_value = api_items

    with patch("httpx.AsyncClient.get", AsyncMock(return_value=mock_response)):
        issues = await client.get_issues("owner", "repo", max_pages=1, per_page=100)
        assert len(issues) == 2
        assert issues[0]["title"] == "Actual Issue"
        assert issues[1]["title"] == "Second Issue"

@pytest.mark.asyncio
async def test_ingestion_service_e2e_workflow(db_session):
    # Setup test job in the database
    job = IngestionJob(
        repository_name="testowner/testrepo",
        status="pending",
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    mock_client = MagicMock(spec=GitHubClient)
    mock_client.get_repository = AsyncMock(return_value={
        "id": 998877,
        "full_name": "testowner/testrepo",
        "name": "testrepo",
        "owner": {"login": "testowner"},
        "description": "Mocked Repo for E2E Test",
        "html_url": "https://github.com/testowner/testrepo",
        "language": "Python",
        "stargazers_count": 120,
        "forks_count": 30,
        "open_issues_count": 1,
    })
    mock_client.get_issues = AsyncMock(return_value=[
        {
            "id": 771122,
            "number": 1,
            "title": "Bug in user profile",
            "body": "Profile image does not load",
            "state": "open",
            "user": {"login": "tester"},
            "labels": [{"name": "bug", "color": "red"}],
            "comments": 3,
            "html_url": "https://github.com/testowner/testrepo/issues/1",
            "created_at": "2026-01-01T12:00:00Z",
            "updated_at": "2026-01-02T12:00:00Z",
            "closed_at": None,
        }
    ])

    service = IngestionService(github_client=mock_client)

    # Patch SessionLocal inside ingestion_service to use our db_session
    with patch("app.services.ingestion_service.SessionLocal", return_value=db_session):
        await service.run_ingestion_job(job_id)

    # Verify job completed
    refreshed_job = db_session.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    assert refreshed_job.status == "completed"
    assert refreshed_job.total_issues_ingested == 1

    # Verify repository saved
    saved_repo = db_session.query(Repository).filter(Repository.full_name == "testowner/testrepo").first()
    assert saved_repo is not None
    assert saved_repo.stargazers_count == 120

    # Verify issue saved
    saved_issue = db_session.query(Issue).filter(Issue.repository_id == saved_repo.id).first()
    assert saved_issue is not None
    assert saved_issue.title == "Bug in user profile"
    assert saved_issue.comments_count == 3
