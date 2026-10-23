from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, inspect, text
from app.database import _ensure_issue_analysis_content_digest
from app.models.code_chunk import CodeChunk
from app.models.code_index_status import CodeIndexStatus
from app.models.issue import Issue
from app.models.repository import Repository
from app.services.triage_service import TriageService

@pytest.fixture
def repo_with_bug_issue(db_session, test_user):
    repo = Repository(
        user_id=test_user.id,
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
    comps = service.extract_mentioned_paths(sample)
    assert any("login.py" in c for c in comps)

def test_triage_service_diagnose_flow(db_session, repo_with_bug_issue):
    _, issue = repo_with_bug_issue
    service = TriageService()
    analysis = service.diagnose_issue(issue, db_session)

    assert analysis.issue_id == issue.id
    assert analysis.category == "bug"
    assert analysis.priority == "P0_CRITICAL"
    assert analysis.stack_trace_detected is True
    assert analysis.reproduction_steps_detected is True
    assert "KeyError" in (analysis.error_type or "")
    # No indexed repository evidence: do not infer affected paths or invent a patch.
    assert analysis.proposed_code_patch is None
    assert analysis.verification_test_code is None
    assert analysis.affected_components == []
    assert analysis.issue_facts
    assert analysis.assumptions
    assert analysis.priority_rationale

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
    assert data["proposed_code_patch"] is None


def test_analysis_refreshes_when_repository_index_finishes(client, auth_headers, db_session, repo_with_bug_issue):
    repo, issue = repo_with_bug_issue
    first = client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)
    assert first.status_code == 200
    assert first.json()["repository_index_status"] == "not_indexed"
    assert first.json()["repository_evidence"] == []

    db_session.add(CodeChunk(
        repository_id=repo.id,
        file_path="app/security.py",
        language="python",
        start_line=45,
        end_line=47,
        chunk_hash="f" * 64,
        content='user_id = payload["user_id"]\nreturn user_id',
    ))
    db_session.add(CodeIndexStatus(
        repository_id=repo.id,
        status="indexed",
        total_files=1,
        indexed_chunks=1,
        last_indexed_at=datetime.now(timezone.utc),
    ))
    db_session.commit()

    updated = client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)
    assert updated.status_code == 200
    data = updated.json()
    assert data["repository_index_status"] == "indexed"
    assert data["affected_components"] == ["app/security.py"]
    assert data["repository_evidence"][0]["file_path"] == "app/security.py"
    assert data["issue_facts"]
    assert data["assumptions"]
    assert len(data["recommendations"]) >= 1


def _track_diagnoses(monkeypatch):
    calls = []
    original = TriageService.diagnose_issue

    def tracked(self, issue, db):
        calls.append(issue.id)
        return original(self, issue, db)

    monkeypatch.setattr(TriageService, "diagnose_issue", tracked)
    return calls


def test_analysis_reuses_saved_result_when_content_and_dependencies_are_unchanged(
    client, auth_headers, db_session, repo_with_bug_issue, monkeypatch
):
    _, issue = repo_with_bug_issue
    calls = _track_diagnoses(monkeypatch)

    first = client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)
    assert first.status_code == 200
    assert calls == [issue.id]
    analysis = issue.analysis[0]
    analyzed_at = analysis.analyzed_at
    expected_digest = TriageService.issue_content_digest(issue.title, issue.body)
    assert analysis.source_content_digest == expected_digest

    second = client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)
    assert second.status_code == 200
    assert calls == [issue.id]
    assert analysis.analyzed_at == analyzed_at


def test_stale_content_digest_refreshes_and_persists_analysis(
    client, auth_headers, db_session, repo_with_bug_issue, monkeypatch
):
    _, issue = repo_with_bug_issue
    client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)
    analysis = issue.analysis[0]
    analysis.source_content_digest = "stale-digest"
    db_session.commit()
    calls = _track_diagnoses(monkeypatch)

    response = client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)

    assert response.status_code == 200
    assert calls == [issue.id]
    assert analysis.source_content_digest == TriageService.issue_content_digest(issue.title, issue.body)


@pytest.mark.parametrize("field", ["title", "body"])
def test_issue_content_change_refreshes_even_when_updated_at_is_unchanged(
    field, client, auth_headers, db_session, repo_with_bug_issue, monkeypatch
):
    _, issue = repo_with_bug_issue
    client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)
    original_updated_at = issue.updated_at
    setattr(issue, field, getattr(issue, field) + "\nUpdated report context.")
    db_session.commit()
    calls = _track_diagnoses(monkeypatch)

    response = client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)

    assert response.status_code == 200
    assert issue.updated_at == original_updated_at
    assert calls == [issue.id]
    assert issue.analysis[0].source_content_digest == TriageService.issue_content_digest(issue.title, issue.body)


def test_legacy_analysis_without_content_digest_refreshes_once(
    client, auth_headers, db_session, repo_with_bug_issue, monkeypatch
):
    _, issue = repo_with_bug_issue
    client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)
    analysis = issue.analysis[0]
    analysis.source_content_digest = None
    db_session.commit()
    calls = _track_diagnoses(monkeypatch)

    first = client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)
    second = client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)

    assert first.status_code == second.status_code == 200
    assert calls == [issue.id]
    assert analysis.source_content_digest == TriageService.issue_content_digest(issue.title, issue.body)


def test_analysis_refreshes_when_model_version_changes(
    client, auth_headers, db_session, repo_with_bug_issue, monkeypatch
):
    _, issue = repo_with_bug_issue
    client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)
    analysis = issue.analysis[0]
    analysis.model_version = "older-triage-version"
    db_session.commit()
    calls = _track_diagnoses(monkeypatch)

    response = client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)

    assert response.status_code == 200
    assert calls == [issue.id]
    assert analysis.model_version == TriageService.MODEL_VERSION


def test_existing_analysis_table_migration_adds_nullable_digest_column_once():
    legacy_engine = create_engine("sqlite:///:memory:")
    with legacy_engine.begin() as conn:
        conn.execute(text("CREATE TABLE issue_analyses (id INTEGER PRIMARY KEY)"))
        _ensure_issue_analysis_content_digest(conn)
        _ensure_issue_analysis_content_digest(conn)
        columns = {column["name"]: column for column in inspect(conn).get_columns("issue_analyses")}

    assert columns["source_content_digest"]["nullable"] is True
    legacy_engine.dispose()

def test_get_issue_analysis_api(client, auth_headers, repo_with_bug_issue):
    _, issue = repo_with_bug_issue
    res = client.get(f"/api/issues/{issue.id}/analysis", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["issue_id"] == issue.id
    assert "root_cause_hypothesis" in data
    assert data["proposed_code_patch"] is None


def test_import_attribute_issue_is_specific_without_claiming_stack_or_priority(db_session, test_user):
    repo = Repository(
        user_id=test_user.id,
        github_repo_id=3939,
        full_name="openai/openai-python",
        name="openai-python",
        owner="openai",
        html_url="https://github.com/openai/openai-python",
    )
    db_session.add(repo)
    db_session.flush()
    issue = Issue(
        repository_id=repo.id,
        github_issue_id=43939,
        issue_number=3939,
        title="import openai fails with older optional aiohttp",
        body="""### Describe the bug
Importing the SDK fails when aiohttp.SocketTimeoutError is unavailable.

### To Reproduce
1. Install aiohttp 3.9.3.
2. Run `python -c \"import openai\"`.

```text
AttributeError: module aiohttp has no attribute SocketTimeoutError
```

The regression test should cover this compatibility behavior; the reported error is not a network timeout.
The issue text mentions src/main.py, but that does not prove it is an affected file.
""",
        state="open",
        labels=[],
        html_url="https://github.com/openai/openai-python/issues/3939",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(issue)
    db_session.commit()
    analysis = TriageService().diagnose_issue(issue, db_session)

    assert analysis.category == "bug"
    assert analysis.stack_trace_detected is False
    assert analysis.reproduction_steps_detected is True
    assert "aiohttp" in analysis.root_cause_hypothesis
    assert "SocketTimeoutError" in analysis.root_cause_hypothesis
    assert analysis.affected_components == []
    assert analysis.repository_evidence == []
    assert analysis.proposed_code_patch is None
    assert any("not run" in item for item in analysis.assumptions)


def test_affected_file_requires_matching_indexed_repository_evidence(db_session, test_user):
    repo = Repository(
        user_id=test_user.id,
        github_repo_id=43940,
        full_name="org/evidence-test",
        name="evidence-test",
        owner="org",
        html_url="https://github.com/org/evidence-test",
    )
    db_session.add(repo)
    db_session.flush()
    issue = Issue(
        repository_id=repo.id,
        github_issue_id=43940,
        issue_number=40,
        title="Module has no attribute SocketTimeoutError",
        body="AttributeError: module aiohttp has no attribute SocketTimeoutError",
        state="open",
        labels=[],
        html_url="https://github.com/org/evidence-test/issues/40",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(issue)
    db_session.flush()
    db_session.add(CodeChunk(
        repository_id=repo.id,
        file_path="src/adapter.py",
        language="python",
        start_line=10,
        end_line=12,
        chunk_hash="e" * 64,
        content="from aiohttp import SocketTimeoutError\nexcept ImportError:\n    SocketTimeoutError = TimeoutError",
    ))
    db_session.commit()

    analysis = TriageService().diagnose_issue(issue, db_session)

    assert analysis.affected_components == ["src/adapter.py"]
    assert analysis.repository_evidence[0]["file_path"] == "src/adapter.py"
    assert analysis.repository_evidence[0]["start_line"] == 10


def test_priority_ignores_low_signal_words_and_code_examples():
    service = TriageService()
    issue_text = "A regression test contains `SocketTimeoutError`. No production outage."
    assert service.estimate_priority("bug", issue_text, True, False)[0] == "P3_LOW"
    assert service.estimate_priority("bug", "Issue blocks release for all users.", True, False)[0] == "P1_HIGH"
    assert service.estimate_priority("bug", "", False, False, [{"name": "priority: P3"}])[0] == "P3_LOW"


def test_category_labels_use_exact_names_not_substrings():
    service = TriageService()
    assert service.classify_category("Debug mode", "", [{"name": "debugging"}], False)[0] == "unknown"
    assert service.classify_category("Issue", "The request fails when saving.", [{"name": "type: bug"}], False)[0] == "bug"
    assert service.classify_category("Issue", "", [{"name": "type: bug"}], False)[0] == "unknown"


def test_fastapi_16451_documentation_report_extracts_context_without_inventing_repro(db_session, test_user):
    repo = Repository(
        user_id=test_user.id,
        github_repo_id=16451,
        full_name="fastapi/fastapi",
        name="fastapi",
        owner="fastapi",
        html_url="https://github.com/fastapi/fastapi",
    )
    db_session.add(repo)
    db_session.flush()
    issue = Issue(
        repository_id=repo.id,
        github_issue_id=16451,
        issue_number=16451,
        title="Docs: note that native OpenTelemetry works on AWS Lambda (Mangum)",
        body="""### Summary
The new OpenTelemetry page doesn't mention serverless / AWS Lambda. I tried it there and it works with only the documented env vars, so a short note would help others wondering about flushing on Lambda.

### Verified setup
- FastAPI `0.142.2` installed as `fastapi[standard]`, no other app code or OTel SDK/instrumentation packages added
- Wrapped with `Mangum` (`handler = Mangum(app)`), AWS Lambda container image, behind API Gateway (HTTP API)
- Only env vars set on the function: `OTEL_SERVICE_NAME`, `OTEL_RESOURCE_ATTRIBUTES`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_EXPORTER_OTLP_HEADERS` (Grafana Cloud OTLP gateway, Basic auth)
- No explicit `force_flush` / shutdown hook in the app

### Result
Request traces and metrics from the Lambda-hosted app arrive and are visible in Grafana Cloud.

### Suggested docs change
Add a short "Serverless / AWS Lambda" note to the OpenTelemetry page.

### Open question
I haven't looked at why no explicit flush is needed. I only verified the setup above.
""",
        state="closed",
        labels=[{"name": "docs"}],
        html_url="https://github.com/fastapi/fastapi/issues/16451",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(issue)
    db_session.commit()

    analysis = TriageService().diagnose_issue(issue, db_session)

    assert analysis.category == "documentation"
    assert analysis.priority == "P3_LOW"
    assert analysis.stack_trace_detected is False
    assert analysis.reproduction_steps_detected is False
    assert analysis.repository_index_status == "not_indexed"
    assert analysis.affected_components == []
    assert analysis.proposed_code_patch is None
    assert "AWS Lambda" in analysis.root_cause_hypothesis
    assert "Mangum" in analysis.root_cause_hypothesis
    assert "Grafana Cloud" in analysis.root_cause_hypothesis
    assert "Author-reported" in analysis.root_cause_hypothesis
    assert "does not establish a runtime root cause" in analysis.root_cause_hypothesis
    assert "Repository-verified findings: none" in analysis.root_cause_hypothesis

    facts = analysis.issue_facts
    assert any("FastAPI `0.142.2`" in fact["value"] for fact in facts if fact["kind"] == "evidence_environment")
    assert any("OTEL_EXPORTER_OTLP_HEADERS" in fact["value"] for fact in facts if fact["kind"] == "evidence_configuration")
    assert any("traces and metrics" in fact["value"] for fact in facts if fact["kind"] == "evidence_observed_results")
    assert not any(fact["kind"] == "evidence_reproduction_steps" for fact in facts)
    assert any("Minimal reproduction" in fact["label"] for fact in analysis.issue_facts if fact["kind"] == "reproduction_limit")

    recommendation = analysis.issue.recommendations[0]
    assert "documentation" in recommendation.action_title.lower()
    assert "Request traces and metrics" in recommendation.rationale
    assert "uncertainty" in recommendation.rationale
    assert "not indexed" in recommendation.rationale


def test_reported_setup_and_result_are_not_reproduction_steps():
    service = TriageService()
    body = """### Environment
- Runtime: Python 3.12

### Result
Requests return a 500 response.
"""

    assert service.has_reproduction_steps(body) is False
    facts = service._reported_context_facts(body)
    assert any("Python 3.12" in fact["value"] for fact in facts if fact["kind"] == "evidence_environment")
    assert any("500 response" in fact["value"] for fact in facts if fact["kind"] == "evidence_observed_results")
    assert any("Minimal reproduction" in fact["label"] for fact in service._reported_context_facts(body) if fact["kind"] == "reproduction_limit")


@pytest.mark.parametrize(
    ("title", "body", "expected"),
    [
        (
            "Request fails after upgrade",
            """### System details
- Python 3.12.2 on Linux
- Client library 4.1.0

### Runtime options
```yaml
retries: 3
endpoint: https://example.test
```

### What I see
The request times out after 30 seconds.

### What I expected
The configured timeout should be applied.

### Reproduction procedure
1. Install the package.
2. Run the application.
3. Send a request.
""",
            {"environment", "configuration", "symptoms", "observed_results", "expected_behavior", "reproduction_steps"},
        ),
        (
            "Unexpected output",
            "Running `python -m sample` on Python 3.11 returns HTTP 503; I expected HTTP 200. Set RETRY_COUNT=3 before starting.",
            {"environment", "configuration", "symptoms", "observed_results", "expected_behavior", "code_examples"},
        ),
        (
            "Client reports a socket error",
            "### Notes\nThe client returns `ConnectionError: refused`. This is the complete error message; no stack trace or logs were captured.\n\n### Details\nThis section describes the deployment context only.",
            {"symptoms"},
        ),
        (
            "Command line hangs",
            "### Verification recipe\n~~~sh\ncurl https://example.test/health\n~~~\n\n### Console output\n```text\n2026-02-01T10:11:12Z ERROR request timed out\n```",
            {"executable_reproductions", "logs"},
        ),
        (
            "Python traceback while processing request",
            "```text\nTraceback (most recent call last):\n  File \"app.py\", line 8, in run\nRuntimeError: failed\n```",
            {"stack_traces", "symptoms"},
        ),
        (
            "Example source code",
            "### Minimal example\n```python\nvalue = calculate(input_value)\n```",
            {"code_examples"},
        ),
    ],
)
def test_extract_evidence_signals_across_issue_formats(title, body, expected):
    signals = TriageService().extract_evidence_signals(title, body)
    assert expected <= {name for name, signal in signals.items() if signal["status"] == "reported"}


@pytest.mark.parametrize(
    ("body", "key", "status"),
    [
        ("The app returns a validation error.", "stack_traces", "not_found"),
        ("No stack trace or logs were captured.", "stack_traces", "explicitly_absent"),
        ("No stack trace or logs were captured.", "logs", "explicitly_absent"),
        ("No expected behavior was specified.", "expected_behavior", "explicitly_absent"),
        ("No Python version or runtime was provided.", "environment", "explicitly_absent"),
        ("", "environment", "not_found"),
    ],
)
def test_evidence_signal_status_distinguishes_absence_from_not_found(body, key, status):
    signals = TriageService().extract_evidence_signals("Issue", body)
    assert signals[key]["status"] == status


@pytest.mark.parametrize(
    ("body", "has_steps"),
    [
        ("### More information\nThis section is not empty.", False),
        ("1. Install package\n2. Run server", True),
        ("### Reproduction notes\nRun the command.\nThen send a request.", True),
        ("### Description\n1. We support three operating systems.\n2. The issue is intermittent.", False),
    ],
)
def test_reproduction_detection_requires_actions_not_merely_content(body, has_steps):
    assert TriageService().has_reproduction_steps(body) is has_steps


@pytest.mark.parametrize(
    ("text", "detected"),
    [
        ("ValueError: invalid value", False),
        ("The server returned HTTP 500", False),
        ("Traceback (most recent call last):\n  File \"app.py\", line 4, in run\nValueError: invalid", True),
        ("TypeError: bad input\n    at parse (src/app.js:10:2)", True),
    ],
)
def test_stack_trace_detection_requires_frame_evidence(text, detected):
    assert TriageService().extract_stack_trace(text)[0] is detected


@pytest.mark.parametrize(
    ("title", "body", "labels", "expected"),
    [
        ("Add retry configuration", "Please add a retry option to the client.", [{"name": "bug"}], "feature_request"),
        ("Service crashes on startup", "The application throws an exception before it can serve requests.", [{"name": "documentation"}], "bug"),
        ("Setup guide omits the installation caveat", "This leaves the installation instructions incomplete.", [], "documentation"),
        ("Could you explain the selection behavior?", "I cannot determine which item is selected.", [], "question"),
        ("Reduce memory use", "Could we reduce peak memory use without changing outputs?", [], "improvement"),
        ("Input handling regression", "No feature is requested; valid input now fails during parsing.", [], "bug"),
        ("Problem report", "The quoted text says ‘this is a bug’, but the report gives no failure details.", [], "unknown"),
        ("Incident", "The service crashes while handling requests.", [{"name": "docs"}], "bug"),
        ("Unclear report", "Please take a look.", [{"name": "bug"}, {"name": "documentation"}], "unknown"),
    ],
)
def test_category_assessment_combines_labels_and_issue_evidence(title, body, labels, expected):
    service = TriageService()
    signals = service.extract_evidence_signals(title, body)
    category, _heuristic_score = service.classify_category(title, body, labels, bool(service.extract_error_type(body)), signals)
    assert category == expected


@pytest.mark.parametrize(
    ("text", "labels", "expected"),
    [
        ("Only one user cannot export, but a workaround is available; there is no outage or data loss.", [{"name": "priority: P0"}], "P2_MEDIUM"),
        ("All customer requests fail and the production service is unavailable.", [], "P1_HIGH"),
        ("A security breach exposes records for all customers.", [], "P0_CRITICAL"),
        ("No data loss; security vulnerability is not present; all users are not affected.", [], "P3_LOW"),
        ("A typo appears in one guide; a workaround exists.", [], "P3_LOW"),
        ("The issue has no impact details.", [{"name": "priority: high"}], "P1_HIGH"),
        ("One user sees a timeout, but a workaround is available.", [{"name": "P0"}, {"name": "P3"}], "P2_MEDIUM"),
        ("The report says functionality is fine and no users are blocked.", [{"name": "priority: P1"}], "P3_LOW"),
    ],
)
def test_priority_uses_impact_scope_negation_and_label_conflicts(text, labels, expected):
    priority, _heuristic_score = TriageService().estimate_priority("bug", text, False, False, labels)
    assert priority == expected


def test_priority_rationale_explains_when_impact_is_insufficient():
    service = TriageService()
    priority, _score = service.estimate_priority("bug", "A failure is reported, but affected users and urgency are unspecified.", False, False)
    rationale = service.priority_rationale(priority, [], "A failure is reported, but affected users and urgency are unspecified.")
    assert priority == "P3_LOW"
    assert "provisional" in rationale
    assert "impact scope" in rationale

