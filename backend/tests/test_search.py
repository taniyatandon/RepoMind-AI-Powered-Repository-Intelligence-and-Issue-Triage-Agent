from datetime import datetime, timezone
import pytest
from app.models.issue import Issue
from app.models.pull_request import PullRequest
from app.models.repository import Repository

@pytest.fixture
def sample_search_data(db_session):
    # 1. Repositories
    repo1 = Repository(
        github_repo_id=1001,
        full_name="tiangolo/fastapi",
        name="fastapi",
        owner="tiangolo",
        description="FastAPI framework, high performance, easy to learn, fast to code, ready for production",
        html_url="https://github.com/tiangolo/fastapi",
        language="Python",
        stargazers_count=70000,
        forks_count=6000,
        open_issues_count=150,
    )
    repo2 = Repository(
        github_repo_id=1002,
        full_name="pallets/flask",
        name="flask",
        owner="pallets",
        description="The Python micro framework for building web applications",
        html_url="https://github.com/pallets/flask",
        language="Python",
        stargazers_count=65000,
        forks_count=15000,
        open_issues_count=80,
    )
    db_session.add_all([repo1, repo2])
    db_session.commit()
    db_session.refresh(repo1)
    db_session.refresh(repo2)

    # 2. Issues
    issue1 = Issue(
        repository_id=repo1.id,
        github_issue_id=2001,
        issue_number=42,
        title="Validation error with query parameters",
        body="When using query parameters with float types, validation fails unexpectedly.",
        state="open",
        author="alice",
        labels=[{"name": "bug", "color": "d73a4a"}],
        comments_count=5,
        html_url="https://github.com/tiangolo/fastapi/issues/42",
    )
    issue2 = Issue(
        repository_id=repo2.id,
        github_issue_id=2002,
        issue_number=101,
        title="Routing performance regression in Flask 3.0",
        body="Url matching takes twice as long after upgrading.",
        state="open",
        author="bob",
        labels=[{"name": "performance", "color": "e4e669"}],
        comments_count=2,
        html_url="https://github.com/pallets/flask/issues/101",
    )
    db_session.add_all([issue1, issue2])

    # 3. Pull Requests
    pr1 = PullRequest(
        repository_id=repo1.id,
        github_pr_id=3001,
        pr_number=55,
        title="Fix query parameter validation float casting",
        body="Resolves #42 by properly parsing float values in query params.",
        state="open",
        is_merged=False,
        author="charlie",
        labels=[{"name": "fix", "color": "0e8a16"}],
        html_url="https://github.com/tiangolo/fastapi/pull/55",
        created_at=datetime.now(timezone.utc),
    )
    pr2 = PullRequest(
        repository_id=repo2.id,
        github_pr_id=3002,
        pr_number=202,
        title="Optimize url rule trie dispatch",
        body="Improves routing speed by 40%.",
        state="merged",
        is_merged=True,
        author="dave",
        labels=[{"name": "optimization", "color": "1d76db"}],
        html_url="https://github.com/pallets/flask/pull/202",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add_all([pr1, pr2])
    db_session.commit()

    return {"repo1": repo1, "repo2": repo2, "issue1": issue1, "issue2": issue2, "pr1": pr1, "pr2": pr2}

def test_search_unauthorized(client):
    res = client.get("/api/search?q=fastapi")
    assert res.status_code == 401

def test_search_missing_query(client, auth_headers):
    res = client.get("/api/search", headers=auth_headers)
    assert res.status_code == 422

def test_search_repositories(client, auth_headers, sample_search_data):
    res = client.get("/api/search?q=fastapi", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "fastapi"
    assert len(data["repositories"]) >= 1
    assert data["repositories"][0]["full_name"] == "tiangolo/fastapi"
    assert data["repositories"][0]["type"] == "repository"
    assert data["repositories"][0]["stargazers_count"] == 70000

def test_search_by_description(client, auth_headers, sample_search_data):
    res = client.get("/api/search?q=micro+framework", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["repositories"]) == 1
    assert data["repositories"][0]["name"] == "flask"

def test_search_issues_by_title(client, auth_headers, sample_search_data):
    res = client.get("/api/search?q=regression", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["issues"]) == 1
    assert data["issues"][0]["issue_number"] == 101
    assert data["issues"][0]["repository_name"] == "pallets/flask"
    assert data["issues"][0]["type"] == "issue"

def test_search_by_issue_number(client, auth_headers, sample_search_data):
    # Searching for #42 or 42
    res = client.get("/api/search?q=%2342", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["issues"]) >= 1
    assert data["issues"][0]["issue_number"] == 42
    assert data["issues"][0]["repository_name"] == "tiangolo/fastapi"

def test_search_pull_requests_by_title(client, auth_headers, sample_search_data):
    res = client.get("/api/search?q=trie+dispatch", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["pull_requests"]) == 1
    assert data["pull_requests"][0]["pr_number"] == 202
    assert data["pull_requests"][0]["repository_name"] == "pallets/flask"
    assert data["pull_requests"][0]["is_merged"] is True

def test_search_by_pr_number(client, auth_headers, sample_search_data):
    res = client.get("/api/search?q=55", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["pull_requests"]) >= 1
    assert data["pull_requests"][0]["pr_number"] == 55

def test_search_multi_category(client, auth_headers, sample_search_data):
    # "validation" matches issue1 title and pr1 title
    res = client.get("/api/search?q=validation", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["issues"]) >= 1
    assert len(data["pull_requests"]) >= 1
    assert data["total"] == len(data["repositories"]) + len(data["issues"]) + len(data["pull_requests"])

def test_search_no_results(client, auth_headers, sample_search_data):
    res = client.get("/api/search?q=nonexistentkeywordxyz123", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert len(data["repositories"]) == 0
    assert len(data["issues"]) == 0
    assert len(data["pull_requests"]) == 0

def test_search_limit(client, auth_headers, sample_search_data):
    res = client.get("/api/search?q=python&limit=1", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["repositories"]) <= 1
