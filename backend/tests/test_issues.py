from datetime import datetime, timezone
import pytest
from app.models.issue import Issue
from app.models.repository import Repository

@pytest.fixture
def repo_with_issues(db_session):
    repo = Repository(
        github_repo_id=555,
        full_name="org/project",
        name="project",
        owner="org",
        html_url="https://github.com/org/project",
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    now = datetime.now(timezone.utc)
    issues_data = [
        {
            "github_issue_id": 1001,
            "issue_number": 1,
            "title": "Fix critical authentication bug",
            "body": "User login crashes when token is expired",
            "state": "open",
            "author": "dev1",
            "labels": [{"name": "bug", "color": "d73a4a"}, {"name": "security", "color": "b60205"}],
        },
        {
            "github_issue_id": 1002,
            "issue_number": 2,
            "title": "Add dark mode toggle to UI",
            "body": "Users requested dark theme support",
            "state": "open",
            "author": "designer",
            "labels": [{"name": "enhancement", "color": "a2eeef"}],
        },
        {
            "github_issue_id": 1003,
            "issue_number": 3,
            "title": "Update installation documentation",
            "body": "Readme steps are outdated for Python 3.13",
            "state": "closed",
            "author": "writer",
            "labels": [{"name": "documentation", "color": "0075ca"}],
        },
        {
            "github_issue_id": 1004,
            "issue_number": 4,
            "title": "Fix memory leak in background worker",
            "body": "Worker does not release session",
            "state": "closed",
            "author": "dev1",
            "labels": [{"name": "bug", "color": "d73a4a"}],
        },
    ]

    for item in issues_data:
        issue = Issue(
            repository_id=repo.id,
            github_issue_id=item["github_issue_id"],
            issue_number=item["issue_number"],
            title=item["title"],
            body=item["body"],
            state=item["state"],
            author=item["author"],
            labels=item["labels"],
            comments_count=2,
            html_url=f"https://github.com/org/project/issues/{item['issue_number']}",
            created_at=now,
            updated_at=now,
        )
        db_session.add(issue)
    db_session.commit()
    return repo

def test_get_issues_empty(client, auth_headers, db_session):
    repo = Repository(
        github_repo_id=999,
        full_name="empty/repo",
        name="repo",
        owner="empty",
        html_url="https://github.com/empty/repo",
    )
    db_session.add(repo)
    db_session.commit()

    res = client.get(f"/api/repositories/{repo.id}/issues", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_pages"] == 1

def test_get_issues_pagination(client, auth_headers, repo_with_issues):
    # Page 1, limit 2
    res = client.get(
        f"/api/repositories/{repo_with_issues.id}/issues?page=1&per_page=2",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 4
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["per_page"] == 2
    assert data["total_pages"] == 2

    # Page 2
    res2 = client.get(
        f"/api/repositories/{repo_with_issues.id}/issues?page=2&per_page=2",
        headers=auth_headers,
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert len(data2["items"]) == 2

def test_get_issues_filter_by_status_open(client, auth_headers, repo_with_issues):
    res = client.get(
        f"/api/repositories/{repo_with_issues.id}/issues?status=open",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert item["state"] == "open"

def test_get_issues_filter_by_status_closed(client, auth_headers, repo_with_issues):
    res = client.get(
        f"/api/repositories/{repo_with_issues.id}/issues?status=closed",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    for item in data["items"]:
        assert item["state"] == "closed"

def test_get_issues_filter_by_title_search(client, auth_headers, repo_with_issues):
    # Search for "memory leak"
    res = client.get(
        f"/api/repositories/{repo_with_issues.id}/issues?title=memory%20leak",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert "memory leak" in data["items"][0]["title"].lower()

def test_get_issues_filter_by_label(client, auth_headers, repo_with_issues):
    res = client.get(
        f"/api/repositories/{repo_with_issues.id}/issues?label=bug",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    for item in data["items"]:
        label_names = [l["name"] for l in item["labels"]]
        assert "bug" in label_names

def test_get_repository_labels_distinct_list(client, auth_headers, repo_with_issues):
    res = client.get(
        f"/api/repositories/{repo_with_issues.id}/labels",
        headers=auth_headers,
    )
    assert res.status_code == 200
    labels = res.json()
    assert set(labels) == {"bug", "enhancement", "documentation", "security"}

def test_get_single_issue_details_success_and_not_found(client, auth_headers, repo_with_issues, db_session):
    first_issue = db_session.query(Issue).filter(Issue.repository_id == repo_with_issues.id).first()
    res = client.get(f"/api/issues/{first_issue.id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == first_issue.id
    assert data["title"] == first_issue.title

    # Nonexistent issue
    res_404 = client.get("/api/issues/99999", headers=auth_headers)
    assert res_404.status_code == 404

def test_get_issue_by_number(client, auth_headers, repo_with_issues, db_session):
    first_issue = db_session.query(Issue).filter(Issue.repository_id == repo_with_issues.id).first()
    res = client.get(
        f"/api/repositories/{repo_with_issues.id}/issues/by-number/{first_issue.issue_number}",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == first_issue.id
    assert data["issue_number"] == first_issue.issue_number

    # 404 for unknown number
    res_404 = client.get(
        f"/api/repositories/{repo_with_issues.id}/issues/by-number/999999",
        headers=auth_headers,
    )
    assert res_404.status_code == 404
