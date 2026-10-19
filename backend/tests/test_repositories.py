import pytest
from app.models.ingestion_job import IngestionJob
from app.models.repository import Repository
from app.schemas.repository import parse_github_repo

def test_parse_and_validate_github_url_formats():
    assert parse_github_repo("facebook/react") == ("facebook", "react")
    assert parse_github_repo("https://github.com/torvalds/linux") == ("torvalds", "linux")
    assert parse_github_repo("http://github.com/tiangolo/fastapi/") == ("tiangolo", "fastapi")
    assert parse_github_repo("github.com/psf/requests.git") == ("psf", "requests")

def test_parse_invalid_github_url():
    with pytest.raises(ValueError):
        parse_github_repo("just-a-string")

    with pytest.raises(ValueError):
        parse_github_repo("https://otherwebsite.com/owner/repo")

def test_add_repository_creates_job_accepted(client, auth_headers):
    res = client.post(
        "/api/repositories",
        headers=auth_headers,
        json={"repo_url_or_name": "https://github.com/fastapi/fastapi"},
    )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "pending"
    assert data["repository_name"] == "fastapi/fastapi"
    assert "job_id" in data

def test_add_repository_duplicate_conflict(client, auth_headers, db_session):
    # Pre-existing repository in database
    repo = Repository(
        github_repo_id=123456,
        full_name="octocat/Hello-World",
        name="Hello-World",
        owner="octocat",
        html_url="https://github.com/octocat/Hello-World",
    )
    db_session.add(repo)
    db_session.commit()

    res = client.post(
        "/api/repositories",
        headers=auth_headers,
        json={"repo_url_or_name": "octocat/Hello-World"},
    )
    assert res.status_code == 409
    assert "already added" in res.json()["detail"].lower()

def test_add_repository_active_job_conflict(client, auth_headers, db_session):
    # Active job already exists
    job = IngestionJob(
        repository_name="facebook/react",
        status="running",
    )
    db_session.add(job)
    db_session.commit()

    res = client.post(
        "/api/repositories",
        headers=auth_headers,
        json={"repo_url_or_name": "facebook/react"},
    )
    assert res.status_code == 409
    assert "already active" in res.json()["detail"].lower()

def test_list_repositories_empty(client, auth_headers):
    res = client.get("/api/repositories", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []

def test_list_repositories_populated(client, auth_headers, db_session):
    repo = Repository(
        github_repo_id=98765,
        full_name="python/cpython",
        name="cpython",
        owner="python",
        html_url="https://github.com/python/cpython",
        language="Python",
        stargazers_count=60000,
    )
    db_session.add(repo)
    db_session.commit()

    res = client.get("/api/repositories", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["full_name"] == "python/cpython"
    assert data[0]["language"] == "Python"
    assert data[0]["stargazers_count"] == 60000

def test_get_repository_by_id_success(client, auth_headers, db_session):
    repo = Repository(
        github_repo_id=111222,
        full_name="vuejs/core",
        name="core",
        owner="vuejs",
        html_url="https://github.com/vuejs/core",
    )
    db_session.add(repo)
    db_session.commit()

    res = client.get(f"/api/repositories/{repo.id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["full_name"] == "vuejs/core"
    assert data["id"] == repo.id

def test_get_repository_by_id_not_found(client, auth_headers):
    res = client.get("/api/repositories/99999", headers=auth_headers)
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()
