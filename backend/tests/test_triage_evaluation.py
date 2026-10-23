"""Held-out, paraphrased triage examples; kept separate from unit fixtures."""

import pytest

from app.services.triage_service import TriageService


@pytest.mark.parametrize(
    ("title", "body", "labels", "expected"),
    [
        (
            "Clarify retry behavior for uploads",
            "The operator guide lists client retries but omits the server-side option. This is a request to explain the configuration; no runtime defect is reported.",
            [{"name": "bug"}],
            "documentation",
        ),
        (
            "Object lookup returns stale values",
            "Observed: lookup can return an older value after update. Expected: subsequent reads return the latest value. Why does this happen?",
            [{"name": "question"}],
            "bug",
        ),
        (
            "Lower memory consumption in serialization",
            "Profiling shows peak memory is higher than required. Could the serializer reduce allocations while keeping output identical?",
            [],
            "improvement",
        ),
        (
            "Expose a bulk export operation",
            "Please add an API operation that exports several selected records in one request.",
            [{"name": "enhancement"}],
            "feature_request",
        ),
        (
            "How should these options be combined?",
            "I am looking for guidance on the supported configuration precedence.",
            [],
            "question",
        ),
    ],
)
def test_held_out_issue_type_examples(title, body, labels, expected):
    service = TriageService()
    signals = service.extract_evidence_signals(title, body)
    category, _score = service.classify_category(title, body, labels, bool(service.extract_error_type(body)), signals)
    assert category == expected


@pytest.mark.parametrize(
    ("text", "labels", "expected"),
    [
        ("Every tenant's requests are blocked in production, with no workaround.", [], "P1_HIGH"),
        ("Only one customer cannot deploy; a workaround is available and there is no outage.", [{"name": "P0"}], "P2_MEDIUM"),
        ("No customers are affected and production is not unavailable.", [{"name": "priority: high"}], "P3_LOW"),
        ("The report describes an urgent production outage.", [], "P1_HIGH"),
        ("A behavior change is reported, but scope and urgency are unspecified.", [], "P3_LOW"),
    ],
)
def test_held_out_priority_examples(text, labels, expected):
    priority, _score = TriageService().estimate_priority("feature_request", text, False, False, labels)
    assert priority == expected
