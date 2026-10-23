from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from app.models.ingestion_job import IngestionJob
from app.models.issue import Issue
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.services.github_client import (
    GitHubClient,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from app.services.ingestion_service import IngestionService

def test_get_ingestion_job_status(client, auth_headers, db_session, test_user):
    job = IngestionJob(
        user_id=test_user.id,
        repository_name="psf/black",
        status="running",
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

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
async def test_github_client_fetches_pull_requests_across_three_linked_pages(caplog):
    caplog.set_level("INFO", logger="app.services.github_client")
    client = GitHubClient()
    first_url = f"{client.BASE_URL}/repos/owner/repo/pulls"
    second_url = f"{first_url}?state=all&per_page=100&page=2"
    third_url = f"{first_url}?state=all&per_page=100&page=3"
    first_page = httpx.Response(
        200,
        json=[{"id": item_id} for item_id in range(100)],
        headers={"Link": f'<{second_url}>; rel="next"'},
        request=httpx.Request("GET", first_url),
    )
    second_page = httpx.Response(
        200,
        json=[{"id": item_id} for item_id in range(100, 200)],
        headers={"Link": f'<{third_url}>; rel="next"'},
        request=httpx.Request("GET", second_url),
    )
    third_page = httpx.Response(
        200,
        json=[{"id": item_id} for item_id in range(200, 209)],
        request=httpx.Request("GET", third_url),
    )
    mocked_get = AsyncMock(side_effect=[first_page, second_page, third_page])

    with patch("httpx.AsyncClient.get", mocked_get):
        pulls = await client.get_pull_requests("owner", "repo")

    assert len(pulls) == 209
    assert pulls[0]["id"] == 0
    assert pulls[-1]["id"] == 208
    assert mocked_get.await_count == 3
    assert mocked_get.await_args_list[1].args[0] == second_url
    assert mocked_get.await_args_list[2].args[0] == third_url
    assert "page=1 records=100 has_next_page=True" in caplog.text
    assert "page=2 records=100 has_next_page=True" in caplog.text
    assert "page=3 records=9 has_next_page=False" in caplog.text
    assert "pages_fetched=3 total_records_fetched=209" in caplog.text

@pytest.mark.asyncio
async def test_github_client_follows_next_link_after_empty_pull_request_page():
    client = GitHubClient()
    first_url = f"{client.BASE_URL}/repos/owner/repo/pulls"
    second_url = f"{first_url}?state=all&per_page=100&page=2"
    first_page = httpx.Response(
        200,
        json=[],
        headers={"Link": f'<{second_url}>; rel="next"'},
        request=httpx.Request("GET", first_url),
    )
    second_page = httpx.Response(
        200,
        json=[{"id": 1}],
        request=httpx.Request("GET", second_url),
    )
    mocked_get = AsyncMock(side_effect=[first_page, second_page])

    with patch("httpx.AsyncClient.get", mocked_get):
        pulls = await client.get_pull_requests("owner", "repo")

    assert pulls == [{"id": 1}]
    assert mocked_get.await_count == 2

@pytest.mark.asyncio
async def test_github_client_stops_when_pagination_has_no_next_link():
    client = GitHubClient()
    url = f"{client.BASE_URL}/repos/owner/repo/pulls"
    response = httpx.Response(
        200,
        json=[{"id": 1}],
        request=httpx.Request("GET", url),
    )
    mocked_get = AsyncMock(return_value=response)

    with patch("httpx.AsyncClient.get", mocked_get):
        pulls = await client.get_pull_requests("owner", "repo")

    assert pulls == [{"id": 1}]
    assert mocked_get.await_count == 1

@pytest.mark.asyncio
async def test_github_client_checks_next_page_when_full_page_has_no_link_header():
    client = GitHubClient()
    url = f"{client.BASE_URL}/repos/owner/repo/pulls"
    full_page = httpx.Response(
        200,
        json=[{"id": item_id} for item_id in range(100)],
        request=httpx.Request("GET", url),
    )
    empty_page = httpx.Response(
        200,
        json=[],
        request=httpx.Request("GET", f"{url}?state=all&per_page=100&page=2&sort=created&direction=desc"),
    )
    mocked_get = AsyncMock(side_effect=[full_page, empty_page])

    with patch("httpx.AsyncClient.get", mocked_get):
        pulls = await client.get_pull_requests("owner", "repo")

    assert len(pulls) == 100
    assert mocked_get.await_count == 2

@pytest.mark.asyncio
async def test_github_client_rejects_failed_later_pull_request_page():
    client = GitHubClient()
    first_url = f"{client.BASE_URL}/repos/owner/repo/pulls"
    second_url = f"{first_url}?state=all&per_page=100&page=2"
    first_page = httpx.Response(
        200,
        json=[{"id": item_id} for item_id in range(100)],
        headers={"Link": f'<{second_url}>; rel="next"'},
        request=httpx.Request("GET", first_url),
    )
    failed_page = httpx.Response(
        403,
        json={"message": "API rate limit exceeded"},
        headers={"x-ratelimit-remaining": "0"},
        request=httpx.Request("GET", second_url),
    )

    with patch("httpx.AsyncClient.get", AsyncMock(side_effect=[first_page, failed_page])):
        with pytest.raises(GitHubRateLimitError):
            await client.get_pull_requests("owner", "repo")

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
    mock_client.get_pull_requests = AsyncMock(return_value=[])

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

@pytest.mark.asyncio
async def test_ingestion_persists_pull_requests_from_every_page(db_session, test_user):
    job = IngestionJob(
        user_id=test_user.id,
        repository_name="testowner/multipage",
        status="pending",
    )
    db_session.add(job)
    db_session.commit()
    job_id = job.id

    page_size = 100
    page_count = 3
    page_items = [
        {
            "id": 800000 + number,
            "number": number,
            "title": f"Pull request {number}",
            "body": None,
            "state": "open" if number % 2 else "closed",
            "user": {"login": "contributor"},
            "labels": [],
            "created_at": "2026-01-01T12:00:00Z",
            "updated_at": "2026-01-02T12:00:00Z",
            "closed_at": None,
            "merged_at": None,
            "html_url": f"https://github.com/testowner/multipage/pull/{number}",
            "diff_url": f"https://github.com/testowner/multipage/pull/{number}.diff",
        }
        for number in range(1, page_size * 2 + 9)
    ]

    def response(url, data, headers=None):
        return httpx.Response(
            200,
            json=data,
            headers=headers,
            request=httpx.Request("GET", url),
        )

    async def mocked_get(url, **kwargs):
        if url.endswith("/repos/testowner/multipage"):
            return response(url, {
                "id": 880001,
                "full_name": "testowner/multipage",
                "name": "multipage",
                "owner": {"login": "testowner"},
                "html_url": "https://github.com/testowner/multipage",
                "open_issues_count": 0,
            })
        if url.endswith("/issues"):
            return response(url, [])
        if url.endswith("/pulls"):
            page = 1
        elif "/pulls?" in url:
            page = int(url.split("page=")[-1].split("&")[0])
        else:
            raise AssertionError(f"Unexpected GitHub API request: {url}")

        start = (page - 1) * page_size
        items = page_items[start : start + page_size]
        headers = {}
        if page < page_count:
            next_url = (
                f"{GitHubClient.BASE_URL}/repos/testowner/multipage/pulls"
                f"?state=all&per_page={page_size}&page={page + 1}"
            )
            headers["Link"] = f'<{next_url}>; rel="next"'
        return response(url, items, headers)

    service = IngestionService(github_client=GitHubClient())
    service.ingest_pull_request_diffs = AsyncMock(return_value=(0, 0))
    with (
        patch("httpx.AsyncClient.get", side_effect=mocked_get),
        patch("app.services.ingestion_service.SessionLocal", return_value=db_session),
    ):
        await service.run_ingestion_job(job_id)

    saved_repo = db_session.query(Repository).filter(
        Repository.full_name == "testowner/multipage"
    ).one()
    assert db_session.query(PullRequest).filter(
        PullRequest.repository_id == saved_repo.id
    ).count() == len(page_items)
    assert db_session.query(PullRequest.github_pr_id).filter(
        PullRequest.repository_id == saved_repo.id
    ).distinct().count() == len(page_items)

@pytest.mark.asyncio
async def test_repeated_ingestion_updates_pull_request_without_duplicates(db_session, test_user):
    job = IngestionJob(
        user_id=test_user.id,
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
        "html_url": "https://github.com/testowner/testrepo",
        "open_issues_count": 1,
    })
    mock_client.get_issues = AsyncMock(return_value=[])
    initial_pr = {
        "id": 998001,
        "number": 17,
        "title": "Initial title",
        "body": "Initial body",
        "state": "open",
        "user": {"login": "contributor"},
        "labels": [],
        "created_at": "2026-01-01T12:00:00Z",
        "updated_at": "2026-01-02T12:00:00Z",
        "closed_at": None,
        "merged_at": None,
        "html_url": "https://github.com/testowner/testrepo/pull/17",
        "diff_url": "https://github.com/testowner/testrepo/pull/17.diff",
    }
    updated_pr = {
        **initial_pr,
        "title": "Updated title",
        "body": "Updated body",
        "state": "closed",
        "updated_at": "2026-02-02T12:00:00Z",
        "closed_at": "2026-02-02T12:00:00Z",
        "merged_at": "2026-02-02T12:00:00Z",
    }
    mock_client.get_pull_requests = AsyncMock(side_effect=[[initial_pr], [updated_pr]])
    service = IngestionService(github_client=mock_client)
    service.ingest_pull_request_diffs = AsyncMock(return_value=(0, 0))

    with patch("app.services.ingestion_service.SessionLocal", return_value=db_session):
        await service.run_ingestion_job(job_id)
        await service.run_ingestion_job(job_id)

    saved_repo = db_session.query(Repository).filter(
        Repository.full_name == "testowner/testrepo"
    ).one()
    stored_prs = db_session.query(PullRequest).filter(
        PullRequest.repository_id == saved_repo.id
    ).all()
    assert len(stored_prs) == 1
    assert stored_prs[0].github_pr_id == 998001
    assert stored_prs[0].title == "Updated title"
    assert stored_prs[0].body == "Updated body"
    assert stored_prs[0].state == "merged"
    assert stored_prs[0].is_merged is True
    assert stored_prs[0].merged_at.isoformat().startswith("2026-02-02")

@pytest.mark.asyncio
async def test_failed_pull_request_sync_preserves_existing_records_and_fails_job(db_session, test_user):
    repo = Repository(
        user_id=test_user.id,
        github_repo_id=998877,
        full_name="testowner/testrepo",
        name="testrepo",
        owner="testowner",
        html_url="https://github.com/testowner/testrepo",
    )
    db_session.add(repo)
    db_session.flush()
    existing_pr = PullRequest(
        repository_id=repo.id,
        github_pr_id=998001,
        pr_number=17,
        title="Previously stored PR",
        state="open",
        is_merged=False,
        labels=[],
        html_url="https://github.com/testowner/testrepo/pull/17",
    )
    job = IngestionJob(
        user_id=test_user.id,
        repository_id=repo.id,
        repository_name="testowner/testrepo",
        status="pending",
    )
    db_session.add_all([existing_pr, job])
    db_session.commit()
    job_id = job.id
    repo_id = repo.id

    mock_client = MagicMock(spec=GitHubClient)
    mock_client.get_repository = AsyncMock(return_value={
        "id": 998877,
        "full_name": "testowner/testrepo",
        "name": "testrepo",
        "owner": {"login": "testowner"},
        "html_url": "https://github.com/testowner/testrepo",
        "open_issues_count": 1,
    })
    mock_client.get_issues = AsyncMock(return_value=[{
        "id": 998002,
        "number": 18,
        "title": "Issue must not be partially imported",
        "state": "open",
        "labels": [],
        "html_url": "https://github.com/testowner/testrepo/issues/18",
    }])
    mock_client.get_pull_requests = AsyncMock(
        side_effect=GitHubRateLimitError("rate limit exceeded", status_code=403)
    )

    with patch("app.services.ingestion_service.SessionLocal", return_value=db_session):
        await IngestionService(github_client=mock_client).run_ingestion_job(job_id)

    saved_job = db_session.query(IngestionJob).filter(IngestionJob.id == job_id).one()
    assert saved_job.status == "failed"
    assert "rate limit" in saved_job.error_message.lower()
    assert db_session.query(PullRequest).filter(PullRequest.repository_id == repo_id).count() == 1
    assert db_session.query(PullRequest).filter(
        PullRequest.github_pr_id == 998001
    ).one().title == "Previously stored PR"
    assert db_session.query(Issue).filter(
        Issue.repository_id == repo_id
    ).count() == 0
