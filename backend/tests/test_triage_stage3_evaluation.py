"""Semantic checks for evidence-grounded Stage 3 explanations and actions."""

import pytest

from app.services.triage_service import TriageService


@pytest.mark.parametrize(
    ("category", "error_type", "text", "required", "forbidden"),
    [
        (
            "bug", "RuntimeError",
            "Observed: export returns an empty file. Expected: all selected rows are included. RuntimeError: writer stopped.",
            ("Author-reported evidence", "actual:", "expected:", "Hypothesis (unverified)", "does not establish the mechanism"),
            ("verified cause", "fix is"),
        ),
        (
            "feature_request", None,
            "Please add a batch endpoint so clients can submit several records together.",
            ("requested behavior", "does not imply a defect", "acceptance criteria"),
            ("root cause is", "bug is caused by"),
        ),
        (
            "documentation", None,
            "The deployment guide omits the reverse proxy configuration needed for this setup.",
            ("documentation context", "does not establish a runtime root cause", "Repository-verified findings: none"),
            ("the problem is in docs/deployment.md",),
        ),
        (
            "question", None,
            "How can a client refresh credentials without restarting?",
            ("asks for information", "does not by itself establish a defect"),
            ("verified root cause", "affected file"),
        ),
        (
            "bug", None,
            "The service worked in version 2.3 and fails after an update. The issue is a regression.",
            ("suggests a regression", "does not by itself identify which change introduced it"),
            ("the update caused",),
        ),
        (
            "unknown", None,
            "This behavior is strange.",
            ("insufficient", "no indexed source evidence"),
            ("root cause is", "affected file is"),
        ),
    ],
)
def test_root_cause_explanations_separate_reports_hypotheses_and_unknowns(category, error_type, text, required, forbidden):
    result = TriageService()._root_cause_hypothesis(category, error_type, text, [])
    lowered = result.lower()
    assert all(term.lower() in lowered for term in required)
    assert all(term.lower() not in lowered for term in forbidden)


def test_fastapi_16417_report_drives_bug_recommendations_without_claiming_source_verification():
    title = "0.142.0: app fails to start when OTEL_EXPORTER_OTLP_ENDPOINT is set but the opentelemetry extra isn't installed"
    body = """### Example Code
```sh
export OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318
uv run --with fastapi==0.142.0 --with uvicorn python -c 'import uvicorn; from fastapi import FastAPI; uvicorn.run(FastAPI(), port=8000)'
```
### Description
The command fails during startup because automatic export requires an optional extra that is not installed. The previous version starts successfully. The endpoint variable may be supplied by the hosting platform even when the app does not request automatic export.
Expected: skip auto configuration when the exporter package is absent, or allow opting out. Other valid protocol/exporter settings also fail during startup.
### Environment
Linux, FastAPI 0.142.0, Python 3.11, Pydantic 2.13.5.
"""
    service = TriageService()
    signals = service.extract_evidence_signals(title, body)
    error_type = service.extract_error_type(body)
    category, _ = service.classify_category(title, body, [{"name": "bug"}], bool(error_type), signals)
    recommendations = service._recommendations(category, error_type, service.has_reproduction_steps(body), [], f"{title}\n{body}", "not_indexed", "P2_MEDIUM", "provisional", signals)
    root = service._root_cause_hypothesis(category, error_type, f"{title}\n{body}", [])
    joined = " ".join(item["action_title"] + " " + item["rationale"] for item in recommendations).lower()
    assert category == "bug"
    assert "startup" in root.lower() or "startup" in joined
    assert "optional extra" in joined or "exporter" in joined
    assert "0.142.0" in joined or "0.142.0" in root
    assert "not been independently reproduced" in root.lower()
    assert "not indexed" in joined
    assert all(path not in joined for path in ("src/main.py", "fastapi/routing.py"))


def test_fastapi_16451_documentation_request_stays_scoped_to_reported_observation():
    title = "Docs: note native telemetry behavior on a serverless adapter"
    body = """### Context
A service runs on a managed function platform behind an HTTP gateway using an ASGI adapter. The documented telemetry environment variables are configured. Request traces and metrics arrive at the configured collector without an explicit flush or shutdown hook.
### Requested change
Add a qualified note to the telemetry guide describing this setup.
### Unknown
The reporter has not determined why export succeeds or whether short invocations and other adapters behave the same way.
"""
    service = TriageService()
    signals = service.extract_evidence_signals(title, body)
    result = service._root_cause_hypothesis("documentation", None, f"{title}\n{body}", [])
    actions = service._recommendations("documentation", None, False, [], f"{title}\n{body}", "not_indexed", "P3_LOW", "provisional", signals)
    rationale = actions[0]["rationale"].lower()
    assert "request traces and metrics" in result.lower()
    assert "does not establish a runtime root cause" in result.lower()
    assert "not been independently reproduced" in result.lower()
    assert "qualified" in rationale or "uncertainty" in rationale
    assert "why" in body.lower() and "does not establish" in result.lower()
    assert "not indexed" in rationale
    assert "docs/" not in rationale


@pytest.mark.parametrize(
    ("category", "body", "expected_action", "must_not_request"),
    [
        ("bug", "Observed: response is truncated. Expected: complete response. Environment: runtime 7.2.", "minimal reproduction", "runtime and dependency versions"),
        ("feature_request", "Please add an export command. Expected: include archived records as an option.", "acceptance criteria", "runtime versions"),
        ("improvement", "Profiling shows repeated allocations under a 10k-row workload.", "baseline", "affected files"),
        ("question", "How do I rotate this credential?", "question", "language, version"),
        ("unknown", "Something looks wrong.", "should have happened", "specific file"),
    ],
)
def test_recommendations_choose_next_step_and_do_not_repeat_provided_details(category, body, expected_action, must_not_request):
    service = TriageService()
    signals = service.extract_evidence_signals("Issue", body)
    recommendation = service._recommendations(category, None, False, [], body, "not_indexed", "P3_LOW", "provisional", signals)[0]
    text = recommendation["action_title"] + " " + recommendation["rationale"]
    assert expected_action in text.lower()
    assert must_not_request not in text.lower()
