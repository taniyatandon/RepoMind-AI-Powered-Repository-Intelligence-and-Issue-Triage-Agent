import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.exc import SQLAlchemyError
from app.models.code_index_status import CodeIndexStatus
from app.models.issue import Issue
from app.models.ingestion_job import IngestionJob
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.security import create_access_token, get_password_hash
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

def test_add_repository_duplicate_conflict(client, auth_headers, db_session, test_user):
    # Pre-existing repository in database
    repo = Repository(
        user_id=test_user.id,
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
    assert "already been added" in res.json()["detail"].lower()


def test_same_repository_can_be_added_by_another_account(client, db_session, test_user):
    existing = Repository(
        user_id=test_user.id,
        github_repo_id=991122,
        full_name="octocat/shared-public-repo",
        name="shared-public-repo",
        owner="octocat",
        html_url="https://github.com/octocat/shared-public-repo",
    )
    second_user = User(
        email="other@repomind.io",
        username="otherdev",
        password_hash=get_password_hash("securepass123"),
        is_active=True,
    )
    db_session.add_all([existing, second_user])
    db_session.commit()
    db_session.refresh(second_user)
    headers = {"Authorization": "Bearer " + create_access_token(
        data={"sub": second_user.email, "user_id": second_user.id}
    )}

    with patch("app.routers.repositories.IngestionService.run_ingestion_job", new_callable=AsyncMock):
        response = client.post(
            "/api/repositories",
            headers=headers,
            json={"repo_url_or_name": "octocat/shared-public-repo"},
        )

    assert response.status_code == 202
    job = db_session.query(IngestionJob).filter(
        IngestionJob.user_id == second_user.id,
        IngestionJob.repository_name == "octocat/shared-public-repo",
    ).one()
    assert job.status == "pending"

def test_add_repository_active_job_conflict(client, auth_headers, db_session, test_user):
    # Active job already exists
    job = IngestionJob(
        user_id=test_user.id,
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

def test_list_repositories_populated(client, auth_headers, db_session, test_user):
    repo = Repository(
        user_id=test_user.id,
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

def test_get_repository_by_id_success(client, auth_headers, db_session, test_user):
    repo = Repository(
        user_id=test_user.id,
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

def test_delete_repository_cascades_owned_data_and_preserves_job_history(
    client, auth_headers, db_session, test_user
):
    repo = Repository(
        user_id=test_user.id,
        github_repo_id=551001,
        full_name="owner/delete-target",
        name="delete-target",
        owner="owner",
        html_url="https://github.com/owner/delete-target",
    )
    unrelated_repo = Repository(
        user_id=test_user.id,
        github_repo_id=551002,
        full_name="owner/keep-target",
        name="keep-target",
        owner="owner",
        html_url="https://github.com/owner/keep-target",
    )
    db_session.add_all([repo, unrelated_repo])
    db_session.flush()

    target_status = CodeIndexStatus(
        repository_id=repo.id,
        status="indexed",
        total_files=3,
        indexed_chunks=4,
    )
    unrelated_status = CodeIndexStatus(
        repository_id=unrelated_repo.id,
        status="indexed",
        total_files=1,
        indexed_chunks=1,
    )
    target_issue = Issue(
        repository_id=repo.id,
        github_issue_id=551101,
        issue_number=1,
        title="Target issue",
        state="open",
        labels=[],
        html_url="https://github.com/owner/delete-target/issues/1",
    )
    unrelated_issue = Issue(
        repository_id=unrelated_repo.id,
        github_issue_id=551102,
        issue_number=1,
        title="Unrelated issue",
        state="open",
        labels=[],
        html_url="https://github.com/owner/keep-target/issues/1",
    )
    target_pr = PullRequest(
        repository_id=repo.id,
        github_pr_id=551201,
        pr_number=2,
        title="Target PR",
        state="open",
        is_merged=False,
        labels=[],
        html_url="https://github.com/owner/delete-target/pull/2",
    )
    unrelated_pr = PullRequest(
        repository_id=unrelated_repo.id,
        github_pr_id=551202,
        pr_number=2,
        title="Unrelated PR",
        state="open",
        is_merged=False,
        labels=[],
        html_url="https://github.com/owner/keep-target/pull/2",
    )
    job = IngestionJob(
        user_id=test_user.id,
        repository_id=repo.id,
        repository_name=repo.full_name,
        status="completed",
    )
    db_session.add_all([
        target_status,
        unrelated_status,
        target_issue,
        unrelated_issue,
        target_pr,
        unrelated_pr,
        job,
    ])
    db_session.commit()
    repo_id = repo.id
    unrelated_repo_id = unrelated_repo.id
    job_id = job.id

    response = client.delete(
        f"/api/repositories/{repo_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert db_session.query(Repository).filter(Repository.id == repo_id).count() == 0
    assert db_session.query(CodeIndexStatus).filter(
        CodeIndexStatus.repository_id == repo_id
    ).count() == 0
    assert db_session.query(Issue).filter(Issue.repository_id == repo_id).count() == 0
    assert db_session.query(PullRequest).filter(
        PullRequest.repository_id == repo_id
    ).count() == 0

    retained_job = db_session.query(IngestionJob).filter(IngestionJob.id == job_id).one()
    assert retained_job.repository_id is None
    assert retained_job.repository_name == "owner/delete-target"
    assert retained_job.status == "completed"

    assert db_session.query(Repository).filter(
        Repository.id == unrelated_repo_id
    ).count() == 1
    assert db_session.query(CodeIndexStatus).filter(
        CodeIndexStatus.repository_id == unrelated_repo_id
    ).count() == 1
    assert db_session.query(Issue).filter(
        Issue.repository_id == unrelated_repo_id
    ).count() == 1
    assert db_session.query(PullRequest).filter(
        PullRequest.repository_id == unrelated_repo_id
    ).count() == 1

def test_delete_repository_rolls_back_on_database_error(
    client, auth_headers, db_session, test_user
):
    repo = Repository(
        user_id=test_user.id,
        github_repo_id=552001,
        full_name="owner/rollback-target",
        name="rollback-target",
        owner="owner",
        html_url="https://github.com/owner/rollback-target",
    )
    db_session.add(repo)
    db_session.flush()
    job = IngestionJob(
        user_id=test_user.id,
        repository_id=repo.id,
        repository_name=repo.full_name,
        status="completed",
    )
    db_session.add(job)
    db_session.commit()
    repo_id = repo.id
    job_id = job.id

    with patch.object(db_session, "commit", side_effect=SQLAlchemyError("database failure")):
        response = client.delete(
            f"/api/repositories/{repo_id}",
            headers=auth_headers,
        )

    assert response.status_code == 500
    assert "database error" in response.json()["detail"].lower()
    assert db_session.query(Repository).filter(Repository.id == repo_id).count() == 1
    retained_job = db_session.query(IngestionJob).filter(IngestionJob.id == job_id).one()
    assert retained_job.repository_id == repo_id
