from datetime import datetime, timezone
import pytest
from app.models.pull_request import PullRequest
from app.models.repository import Repository

@pytest.fixture
def repo_with_prs(db_session):
    repo = Repository(
        github_repo_id=123999,
        full_name="org/pr-testing",
        name="pr-testing",
        owner="org",
        html_url="https://github.com/org/pr-testing",
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    now = datetime.now(timezone.utc)
    prs_data = [
        {
            "github_pr_id": 901,
            "pr_number": 10,
            "title": "Fix token validation memory leak",
            "body": "Fixes #42 by closing database session.",
            "state": "merged",
            "is_merged": True,
            "author": "alice",
        },
        {
            "github_pr_id": 902,
            "pr_number": 11,
            "title": "Add dark mode toggle to UI navbar",
            "body": "Implements theme switcher.",
            "state": "open",
            "is_merged": False,
            "author": "bob",
        },
        {
            "github_pr_id": 903,
            "pr_number": 12,
            "title": "Update installation docs for Python 3.13",
            "body": "Updates setup guide.",
            "state": "closed",
            "is_merged": False,
            "author": "charlie",
        },
    ]

    for item in prs_data:
        pr = PullRequest(
            repository_id=repo.id,
            github_pr_id=item["github_pr_id"],
            pr_number=item["pr_number"],
            title=item["title"],
            body=item["body"],
            state=item["state"],
            is_merged=item["is_merged"],
            author=item["author"],
            html_url=f"https://github.com/org/pr-testing/pull/{item['pr_number']}",
            created_at=now,
            updated_at=now,
        )
        db_session.add(pr)
    db_session.commit()
    return repo

def test_get_pull_requests_empty(client, auth_headers, db_session):
    repo = Repository(
        github_repo_id=8888,
        full_name="empty/pr-repo",
        name="pr-repo",
        owner="empty",
        html_url="https://github.com/empty/pr-repo",
    )
    db_session.add(repo)
    db_session.commit()

    res = client.get(f"/api/repositories/{repo.id}/pulls", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []

def test_get_pull_requests_pagination(client, auth_headers, repo_with_prs):
    res = client.get(
        f"/api/repositories/{repo_with_prs.id}/pulls?page=1&per_page=2",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["per_page"] == 2
    assert data["total_pages"] == 2

def test_get_pull_requests_filter_merged(client, auth_headers, repo_with_prs):
    res = client.get(
        f"/api/repositories/{repo_with_prs.id}/pulls?status=merged",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["is_merged"] is True
    assert data["items"][0]["pr_number"] == 10

def test_get_pull_requests_filter_open(client, auth_headers, repo_with_prs):
    res = client.get(
        f"/api/repositories/{repo_with_prs.id}/pulls?status=open",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["state"] == "open"
    assert data["items"][0]["pr_number"] == 11

def test_get_pull_requests_filter_title(client, auth_headers, repo_with_prs):
    res = client.get(
        f"/api/repositories/{repo_with_prs.id}/pulls?title=dark%20mode",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert "dark mode" in data["items"][0]["title"].lower()

def test_get_single_pull_request_details(client, auth_headers, repo_with_prs, db_session):
    first_pr = db_session.query(PullRequest).filter(PullRequest.repository_id == repo_with_prs.id).first()
    res = client.get(f"/api/pulls/{first_pr.id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == first_pr.id
    assert data["title"] == first_pr.title

    # 404
    res_404 = client.get("/api/pulls/99999", headers=auth_headers)
    assert res_404.status_code == 404

def test_get_pull_request_commits_and_diffs(client, auth_headers, repo_with_prs, db_session):
    from app.models.commit import Commit
    from app.models.code_diff import CodeDiff

    pr = db_session.query(PullRequest).filter(PullRequest.repository_id == repo_with_prs.id).first()
    now = datetime.now(timezone.utc)

    # Insert commit
    commit = Commit(
        repository_id=repo_with_prs.id,
        pull_request_id=pr.id,
        sha="abcdef1234567890abcdef1234567890abcdef12",
        message="Fix connection leak in pool",
        author_name="Alice Dev",
        author_email="alice@example.com",
        committed_at=now,
        html_url="https://github.com/org/pr-testing/commit/abcdef12",
    )
    db_session.add(commit)

    # Insert code diff
    diff = CodeDiff(
        repository_id=repo_with_prs.id,
        pull_request_id=pr.id,
        commit_sha=commit.sha,
        filename="src/connection.py",
        status="modified",
        additions=15,
        deletions=3,
        changes_count=18,
        diff_content="@@ -10,3 +10,15 @@ def connect():\n+    pool.close()",
    )
    db_session.add(diff)
    db_session.commit()

    # 1. Test commits endpoint
    res_commits = client.get(f"/api/pulls/{pr.id}/commits", headers=auth_headers)
    assert res_commits.status_code == 200
    commits_data = res_commits.json()
    assert len(commits_data) == 1
    assert commits_data[0]["sha"] == commit.sha
    assert commits_data[0]["message"] == "Fix connection leak in pool"

    # 2. Test diffs endpoint
    res_diffs = client.get(f"/api/pulls/{pr.id}/diffs", headers=auth_headers)
    assert res_diffs.status_code == 200
    diffs_data = res_diffs.json()
    assert len(diffs_data) == 1
    assert diffs_data[0]["filename"] == "src/connection.py"
    assert diffs_data[0]["additions"] == 15
    assert diffs_data[0]["deletions"] == 3

    # 3. Test changes summary endpoint
    res_changes = client.get(f"/api/pulls/{pr.id}/changes?auto_sync=false", headers=auth_headers)
    assert res_changes.status_code == 200
    changes_data = res_changes.json()
    assert changes_data["pr_id"] == pr.id
    assert changes_data["total_commits"] == 1
    assert changes_data["total_files_changed"] == 1
    assert changes_data["total_additions"] == 15
    assert changes_data["total_deletions"] == 3
    assert len(changes_data["commits"]) == 1
    assert len(changes_data["files"]) == 1
