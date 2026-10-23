"""Focused regressions for general triage reliability gaps found in Stage 4."""

from datetime import datetime, timezone

import pytest

from app.models.code_chunk import CodeChunk
from app.models.issue import Issue
from app.models.repository import Repository
from app.services.triage_service import TriageService


@pytest.mark.parametrize(
    ("body", "required"),
    [
        (
            "Runtime: Rust 1.82. Actual output: the upload returns success with zero bytes. "
            "Expected output: all parts are present. Reproduce by creating an upload and completing it.",
            {"environment", "observed_results", "expected_behavior", "reproduction_steps"},
        ),
        (
            "The client reports a timeout after deployment. Expected behavior: the request should finish.\n"
            "Reproduce by sending a request with the supplied configuration.",
            {"symptoms", "expected_behavior", "reproduction_steps"},
        ),
        (
            "Environment: Linux. Only environment variables configured: `TRACE_ENDPOINT`, `TRACE_HEADERS`.",
            {"environment", "configuration"},
        ),
        (
            "No exception, failed request, or incorrect result is reported; I am asking whether this is expected.",
            set(),
        ),
    ],
)
def test_extraction_handles_inline_fields_and_scoped_negation(body, required):
    service = TriageService()
    signals = service.extract_evidence_signals("", body)
    reported = {key for key, value in signals.items() if value["status"] == "reported"}
    assert required <= reported
    if not required:
        assert "symptoms" not in reported


@pytest.mark.parametrize(
    ("title", "body", "labels", "expected"),
    [
        (
            "Add a separator option to the export command",
            "Please support selecting a record separator while keeping the existing default.",
            [{"name": "bug"}],
            "feature_request",
        ),
        (
            "Rendering fails for an empty table",
            "The renderer stops and returns an IndexError for a zero-row table.",
            [],
            "bug",
        ),
        (
            "Does the dashboard remain open when a filter is empty?",
            "No exception, failed request, or incorrect result is reported; I am asking whether this is expected.",
            [{"name": "bug"}],
            "question",
        ),
        (
            "Summary and output disagree about stream status",
            "The summary says the stream completed successfully, while the output ends with DecodeError. "
            "I cannot tell whether both refer to the same input.",
            [{"name": "bug"}, {"name": "question"}],
            "unknown",
        ),
    ],
)
def test_category_uses_reported_request_and_conflicting_evidence(title, body, labels, expected):
    service = TriageService()
    signals = service.extract_evidence_signals(title, body)
    category, _ = service.classify_category(title, body, labels, False, signals)
    assert category == expected


def test_isolated_error_or_stack_does_not_raise_priority_without_impact():
    service = TriageService()
    assert service.estimate_priority("bug", "IndexError: empty table", True, True)[0] == "P3_LOW"


def test_repository_evidence_never_uses_another_repositories_index(db_session, test_user):
    repos = []
    for index, name in enumerate(("reported", "unrelated")):
        repo = Repository(
            user_id=test_user.id,
            github_repo_id=8100 + index,
            full_name=f"fixture/{name}",
            name=name,
            owner="fixture",
            html_url=f"https://github.com/fixture/{name}",
        )
        db_session.add(repo)
        db_session.flush()
        repos.append(repo)
    issue = Issue(
        repository_id=repos[0].id,
        github_issue_id=9001,
        issue_number=1,
        title="Parser raises DecodeError on incomplete frame",
        body="DecodeError: incomplete frame",
        state="open",
        labels=[],
        html_url="https://github.com/fixture/reported/issues/1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(issue)
    db_session.flush()
    db_session.add(CodeChunk(
        repository_id=repos[1].id,
        file_path="src/unrelated_parser.py",
        language="python",
        start_line=3,
        end_line=4,
        chunk_hash="a" * 64,
        content="DecodeError incomplete frame",
    ))
    db_session.commit()

    analysis = TriageService().diagnose_issue(issue, db_session)
    assert analysis.repository_evidence == []
    assert analysis.affected_components == []
