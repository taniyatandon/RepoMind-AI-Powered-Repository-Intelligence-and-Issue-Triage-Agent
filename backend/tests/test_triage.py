from datetime import datetime, timezone
import pytest
from app.models.issue import Issue
from app.models.repository import Repository
from app.services.triage_service import TriageService

@pytest.fixture
def repo_with_bug_issue(db_session):
    repo = Repository(
        github_repo_id=7788,
        full_name="org/debugger-test",
        name="debugger-test",
        owner="org",
        html_url="https://github.com/org/debugger-test",
    )
    db_session.add(repo)
    db_session.commit()
    db_session.refresh(repo)

    now = datetime.now(timezone.utc)
    issue = Issue(
        repository_id=repo.id,
        github_issue_id=99001,
        issue_number=42,
        title="Uncaught KeyError: 'user_id' during token validation",
        body="""
When refreshing the token, the backend crashes with a critical exception.

Steps to reproduce:
1. Log in with expired credentials
2. Request refreshed bearer token

```python
Traceback (most recent call last):
  File "app/security.py", line 45, in decode_access_token
    user_id = payload["user_id"]
KeyError: 'user_id'
```

This causes security bypass or server crash.
""",
        state="open",
        author="bugreporter",
        labels=[{"name": "bug", "color": "d73a4a"}],
        comments_count=1,
        html_url="https://github.com/org/debugger-test/issues/42",
        created_at=now,
        updated_at=now,
    )
    db_session.add(issue)
    db_session.commit()
    db_session.refresh(issue)
    return repo, issue

def test_triage_stack_trace_and_error_extraction():
    service = TriageService()
    sample_text = """
Error encountered:
Traceback (most recent call last):
  File "app/main.py", line 12, in root
    x = 1 / 0
ZeroDivisionError: division by zero
"""
    has_tb, tb = service.extract_stack_trace(sample_text)
    assert has_tb is True
    assert "ZeroDivisionError" in tb

    err = service.extract_error_type(sample_text)
    assert "ZeroDivisionError" in err

def test_triage_reproduction_and_components_detection():
    service = TriageService()
    sample = """
How to reproduce:
1. Run server
2. Send request to auth/login.py
"""
    assert service.has_reproduction_steps(sample) is True
    comps = service.extract_affected_components(sample)
    assert any("login.py" in c for c in comps)

def test_triage_service_diagnose_flow(db_session, repo_with_bug_issue):
    _, issue = repo_with_bug_issue
    service = TriageService()
    analysis = service.diagnose_issue(issue, db_session)

    assert analysis.issue_id == issue.id
    assert analysis.category == "bug"
    assert analysis.priority in ["P0_CRITICAL", "P1_HIGH"]
    assert analysis.stack_trace_detected is True
    assert analysis.reproduction_steps_detected is True
    assert "KeyError" in (analysis.error_type or "")
    # Verify code solution generated
    assert analysis.proposed_code_patch is not None
    assert "--- a/" in analysis.proposed_code_patch
    assert analysis.verification_test_code is not None
    assert "def test_" in analysis.verification_test_code

    # Verify recommendations saved
    assert len(analysis.issue.recommendations) > 0

def test_diagnose_single_issue_api(client, auth_headers, repo_with_bug_issue):
    _, issue = repo_with_bug_issue
    res = client.post(f"/api/issues/{issue.id}/diagnose", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["issue_id"] == issue.id
    assert data["category"] == "bug"
    assert data["stack_trace_detected"] is True
    assert data["proposed_code_patch"] is not None
    assert len(data["recommendations"]) >= 1

def test_get_issue_analysis_api(client, auth_headers, repo_with_bug_issue):
    _, issue = repo_with_bug_issue
    res = client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["issue_id"] == issue.id
    assert "root_cause_hypothesis" in data
    assert data["proposed_code_patch"] is not None

