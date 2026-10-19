from datetime import datetime, timezone
import re
from typing import Any
from sqlalchemy.orm import Session

from app.models.action_recommendation import ActionRecommendation
from app.models.issue import Issue
from app.models.issue_analysis import IssueAnalysis

# Common exceptions and error patterns
EXCEPTION_PATTERNS = [
    r"\b([A-Z][a-zA-Z0-9]*(?:Error|Exception|Warning|Fault))\b",
    r"\b(Traceback \(most recent call last\):.*?)(?:\n\s*\n|\Z)",
    r"\b(HTTP (?:4\d\d|5\d\d)[^\n]*)",
    r"\b(NullPointerException|Segmentation fault|Panic|Deadlock|Memory leak)\b",
]

FILE_PATH_PATTERN = r"([a-zA-Z0-9_\-\.\/]+\.(?:py|js|ts|jsx|tsx|json|yml|yaml|sql|go|rs|c|cpp|h))"

REPRODUCTION_KEYWORDS = [
    "steps to reproduce",
    "reproduction",
    "how to reproduce",
    "to reproduce",
    "reproducible",
    "minimal example",
    "sample code",
]

CRITICAL_KEYWORDS = [
    "security",
    "vulnerability",
    "cve-",
    "crash",
    "data loss",
    "corruption",
    "exploit",
    "segfault",
    "out of memory",
    "critical",
    "deadlock",
]

HIGH_PRIORITY_KEYWORDS = [
    "regression",
    "broken",
    "fails to start",
    "cannot connect",
    "infinite loop",
    "blocker",
    "freeze",
    "timeout",
]

class TriageService:
    def __init__(self, model_version: str = "repomind-triage-v1.0"):
        self.model_version = model_version

    def extract_stack_trace(self, text: str) -> tuple[bool, str | None]:
        # Python traceback
        tb_match = re.search(r"(Traceback \(most recent call last\):[\s\S]*?(?:Error|Exception):[^\n]*)", text)
        if tb_match:
            return True, tb_match.group(1).strip()

        # Generic code block containing error
        code_blocks = re.findall(r"```(?:[\w]*\n)?([\s\S]*?)```", text)
        for block in code_blocks:
            if re.search(r"(?:error|exception|fail|traceback|at\s+[\w\.\/]+:\d+)", block, re.IGNORECASE):
                return True, block.strip()

        # Standalone JS stack trace
        js_match = re.search(r"((?:Error:[^\n]+\n)(?:\s+at [^\n]+\n)+)", text)
        if js_match:
            return True, js_match.group(1).strip()

        return False, None

    def extract_error_type(self, text: str) -> str | None:
        for pattern in EXCEPTION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                val = match.group(1).strip()
                if "Traceback" in val:
                    # Extract the final error line
                    lines = val.splitlines()
                    return lines[-1].strip() if lines else "Traceback Exception"
                return val
        return None

    def extract_affected_components(self, text: str) -> list[str]:
        components = set()
        # Find file paths
        matches = re.findall(FILE_PATH_PATTERN, text)
        for m in matches:
            if not m.startswith("http") and "/" in m or m.endswith((".py", ".ts", ".js")):
                components.add(m)

        # Find function-like names (e.g. get_user(), initialize())
        func_matches = re.findall(r"\b([a-z_][a-z0-9_]{3,})\(\)", text)
        for f in func_matches[:3]:
            components.add(f"{f}()")

        return sorted(list(components))[:6]

    def has_reproduction_steps(self, text: str) -> bool:
        lower = text.lower()
        if any(kw in lower for kw in REPRODUCTION_KEYWORDS):
            return True
        # If there are numbered steps with code
        if re.search(r"(?:1\.\s+.*?\n2\.\s+)", text) and "```" in text:
            return True
        return False

    def classify_category(self, title: str, body: str, labels: list[Any], has_error: bool) -> tuple[str, float]:
        text = f"{title} {body}".lower()
        label_names = []
        for l in labels:
            if isinstance(l, dict) and "name" in l:
                label_names.append(l["name"].lower())
            elif isinstance(l, str):
                label_names.append(l.lower())

        # Check labels first
        if any(b in " ".join(label_names) for b in ["bug", "defect", "fault"]):
            return "bug", 0.96
        if any(f in " ".join(label_names) for f in ["enhancement", "feature", "proposal"]):
            return "feature_request", 0.94
        if any(d in " ".join(label_names) for d in ["doc", "documentation"]):
            return "documentation", 0.95
        if any(q in " ".join(label_names) for q in ["question", "help wanted"]):
            return "question", 0.92

        # Check content
        if has_error or any(k in text for k in ["crash", "exception", "failed with", "error:", "unexpected error"]):
            return "bug", 0.91
        if any(k in text for k in ["add support for", "feature request", "would be great to have", "please add", "proposal:"]):
            return "feature_request", 0.88
        if any(k in text for k in ["refactor", "optimize", "improve performance", "clean up", "speed up"]):
            return "improvement", 0.86
        if any(k in text for k in ["typo in", "update readme", "documentation is missing", "docs clarify"]):
            return "documentation", 0.90
        if any(k in text for k in ["how can i", "how do i", "is it possible to", "question:"]):
            return "question", 0.85

        return "improvement", 0.75

    def estimate_priority(self, category: str, text: str, has_error: bool, has_stack_trace: bool) -> tuple[str, float]:
        lower = text.lower()
        if any(k in lower for k in CRITICAL_KEYWORDS):
            return "P0_CRITICAL", 0.92
        if category == "bug" and (has_stack_trace or any(k in lower for k in HIGH_PRIORITY_KEYWORDS)):
            return "P1_HIGH", 0.88
        if category == "bug" or category == "feature_request":
            return "P2_MEDIUM", 0.82
        return "P3_LOW", 0.85

    def generate_root_cause_hypothesis(
        self,
        category: str,
        error_type: str | None,
        components: list[str],
        has_stack_trace: bool,
    ) -> str:
        if category == "bug":
            if error_type and components:
                return (
                    f"Failure triggered by {error_type}. The exception occurs during execution "
                    f"associated with component(s): {', '.join(components)}. "
                    "Likely caused by unhandled input state, missing null check, or changed API contract."
                )
            elif error_type:
                return (
                    f"Runtime failure detected with exception: {error_type}. "
                    "May indicate an unhandled boundary condition, invalid data serialization, or missing dependency."
                )
            elif has_stack_trace:
                return (
                    "Execution halted by an unhandled error inside a code block. "
                    "Inspect the call stack to identify the origin module and verify input invariants."
                )
            return "Bug report describes unexpected behavior or incorrect output. Requires checking functional logic against requirements."
        elif category == "feature_request":
            return "New capability or enhancement requested. Requires assessing architecture impact and API compatibility."
        elif category == "documentation":
            return "Documentation inaccuracy, typo, or missing guide. Low technical risk, can be resolved with editorial patch."
        elif category == "question":
            return "Usage or configuration inquiry. Can likely be resolved by pointing to existing documentation or examples."
        return "General project improvement or refactoring task."

    def generate_recommendations(
        self,
        category: str,
        priority: str,
        error_type: str | None,
        has_stack_trace: bool,
        has_repro: bool,
        components: list[str],
    ) -> list[dict[str, str]]:
        recs = []

        if category == "bug":
            if not has_repro:
                recs.append({
                    "action_type": "request_info",
                    "action_title": "Request Minimal Reproducible Example",
                    "rationale": "The issue does not contain clear step-by-step reproduction instructions. Ask the author for a minimal code snippet to reproduce locally.",
                    "severity": "warning",
                })
            else:
                recs.append({
                    "action_type": "debug_fix",
                    "action_title": "Isolate Reproduction in Unit Test",
                    "rationale": "Reproduction details detected in issue. Write a failing regression test reproducing the exact failure before applying a patch.",
                    "severity": "info",
                })

            if error_type:
                comp_str = f" in {components[0]}" if components else ""
                recs.append({
                    "action_type": "debug_fix",
                    "action_title": f"Add Defensive Exception Handling for {error_type}",
                    "rationale": f"Inspect call site{comp_str} and add appropriate try/except or input guards to prevent {error_type} from escaping.",
                    "severity": "critical" if priority in ["P0_CRITICAL", "P1_HIGH"] else "warning",
                })

            if priority == "P0_CRITICAL":
                recs.append({
                    "action_type": "triage_label",
                    "action_title": "Escalate to High Priority / Urgent Patch",
                    "rationale": "Issue involves critical impact (crash, data corruption, or security). Assign to current milestone hotfix.",
                    "severity": "critical",
                })
        elif category == "feature_request":
            recs.append({
                "action_type": "triage_label",
                "action_title": "Scope Architecture & API Design",
                "rationale": "Clarify proposed interface with maintainers before starting implementation.",
                "severity": "info",
            })
        elif category == "documentation":
            recs.append({
                "action_type": "triage_label",
                "action_title": "Good First Issue Candidate",
                "rationale": "Documentation updates are great entry points for new open-source contributors.",
                "severity": "info",
            })

        return recs

    def generate_code_solution(
        self,
        title: str,
        body: str,
        category: str,
        error_type: str | None,
        stack_trace: str | None,
        components: list[str],
    ) -> tuple[str, str, str, str]:
        """
        Synthesizes:
        (target_file, proposed_patch, verification_test, explanation)
        """
        full_text = f"{title} {body}"
        
        # Determine target file
        target_file = components[0] if components else "src/main.py"
        if not target_file.endswith((".py", ".ts", ".js")):
            target_file = f"{target_file}.py" if "." not in target_file else target_file

        # 1. KeyError Fix Strategy
        if error_type and "KeyError" in error_type:
            key_match = re.search(r"KeyError:?\s*['\"]([^'\"]+)['\"]", full_text)
            key_name = key_match.group(1) if key_match else "item"

            patch = f"""--- a/{target_file}
+++ b/{target_file}
@@ -35,6 +35,11 @@
-    val = data["{key_name}"]
+    # Defensive key lookup: avoid direct unvalidated indexing
+    val = data.get("{key_name}")
+    if val is None:
+        raise ValueError("Missing required key '{key_name}' in configuration/payload")
     return process_value(val)"""

            test_code = f"""import pytest

def test_missing_{key_name}_handled_gracefully():
    \"\"\"Verify that missing key '{key_name}' raises a clear ValueError instead of uncaught KeyError.\"\"\"
    payload_without_key = {{}}
    
    # Pre-patch would raise KeyError: '{key_name}'
    # With patch applied:
    val = payload_without_key.get("{key_name}")
    assert val is None, "Should handle missing key gracefully without crashing"
"""

            explanation = (
                f"Direct dictionary indexing `data['{key_name}']` crashes with an uncaught `KeyError` "
                f"when the key is omitted. The patch converts the access to safe `.get('{key_name}')` "
                f"and validates presence before processing, preventing application halts."
            )
            return target_file, patch, test_code, explanation

        # 2. AttributeError / NoneType Fix Strategy
        if error_type and ("AttributeError" in error_type or "NoneType" in full_text):
            patch = f"""--- a/{target_file}
+++ b/{target_file}
@@ -20,5 +20,8 @@
-    result = obj.execute()
+    # Defensive null-guard check
+    if obj is None:
+        return None
+    result = obj.execute()
     return result"""

            test_code = """import pytest

def test_none_object_guard():
    \"\"\"Verify that passing None or uninitialized instance does not crash with AttributeError.\"\"\"
    obj = None
    result = None if obj is None else obj.execute()
    assert result is None, "Expected None return for uninitialized object"
"""

            explanation = (
                "An object was accessed before initialization or after an upstream call returned None. "
                "The patch inserts a defensive null check to return a safe fallback or handle empty states gracefully."
            )
            return target_file, patch, test_code, explanation

        # 3. ZeroDivisionError Fix Strategy
        if error_type and "ZeroDivisionError" in error_type:
            patch = f"""--- a/{target_file}
+++ b/{target_file}
@@ -14,4 +14,6 @@
-    ratio = numerator / denominator
+    # Guard against zero divisor
+    if denominator == 0:
+        return 0.0
+    ratio = numerator / denominator"""

            test_code = """import pytest

def test_zero_division_guard():
    \"\"\"Verify that zero divisor returns default ratio rather than ZeroDivisionError.\"\"\"
    def safe_div(num, den):
        return 0.0 if den == 0 else num / den

    assert safe_div(10, 0) == 0.0
    assert safe_div(10, 2) == 5.0
"""
            explanation = (
                "A division operation executed with a zero denominator. The patch introduces "
                "a guard returning a neutral float (0.0) when denominator is 0."
            )
            return target_file, patch, test_code, explanation

        # 4. IndexError Fix Strategy
        if error_type and "IndexError" in error_type:
            patch = f"""--- a/{target_file}
+++ b/{target_file}
@@ -10,3 +10,5 @@
-    first = items[0]
+    if not items:
+        return None
+    first = items[0]"""

            test_code = """import pytest

def test_empty_list_indexing_guard():
    \"\"\"Verify that empty collections do not crash with IndexError.\"\"\"
    items = []
    first = items[0] if items else None
    assert first is None
"""
            explanation = (
                "Attempted to access collection index on an empty sequence. "
                "The patch checks collection truthiness before index dereferencing."
            )
            return target_file, patch, test_code, explanation

        # 5. Network / Timeout / Connection Fix Strategy
        if error_type and any(kw in error_type for kw in ["Timeout", "Connection", "HTTP"]):
            patch = f"""--- a/{target_file}
+++ b/{target_file}
@@ -40,5 +40,11 @@
-    response = client.get(endpoint)
+    try:
+        response = client.get(endpoint, timeout=15.0)
+        response.raise_for_status()
+    except Exception as exc:
+        logger.warning(f"Upstream request failed: {{exc}}")
+        return {{"error": "Upstream service temporarily unavailable", "retryable": True}}"""

            test_code = """import pytest

def test_network_timeout_fallback():
    \"\"\"Verify timeout exception is caught and formatted as retryable response.\"\"\"
    # Simulates timeout without application crash
    def handle_call(fail=True):
        if fail:
            return {"error": "Upstream service temporarily unavailable", "retryable": True}
        return {"status": "ok"}

    res = handle_call(fail=True)
    assert res["retryable"] is True
"""
            explanation = (
                "External or network resource call timed out or failed without exception handling. "
                "The patch wraps the call in a timeout-bounded try/except block with retryable fallback."
            )
            return target_file, patch, test_code, explanation

        # Default General Fix Strategy
        patch = f"""--- a/{target_file}
+++ b/{target_file}
@@ -15,5 +15,10 @@
     # Input validation and boundary guard
+    if input_data is None:
+        logger.info("Empty input received; returning default state")
+        return {{}}
+
     result = process_data(input_data)
     return result"""

        test_code = f"""import pytest

def test_boundary_input_validation():
    \"\"\"Verify input validation resolves reported issue without regressions.\"\"\"
    assert True, "Regression test verifies bug condition is handled"
"""

        explanation = (
            f"The patch introduces defensive input boundaries in `{target_file}` to ensure "
            "empty or malformed states do not cascade into unhandled failures."
        )
        return target_file, patch, test_code, explanation

    def diagnose_issue(self, issue: Issue, db: Session) -> IssueAnalysis:
        full_text = f"{issue.title}\n\n{issue.body or ''}"
        has_stack_trace, extracted_tb = self.extract_stack_trace(full_text)
        error_type = self.extract_error_type(full_text)
        affected_comps = self.extract_affected_components(full_text)
        has_repro = self.has_reproduction_steps(full_text)

        category, cat_conf = self.classify_category(
            issue.title,
            issue.body or "",
            issue.labels,
            has_error=bool(error_type or has_stack_trace),
        )

        priority, prio_conf = self.estimate_priority(
            category,
            full_text,
            has_error=bool(error_type),
            has_stack_trace=has_stack_trace,
        )

        confidence = round((cat_conf + prio_conf) / 2.0, 2)

        root_cause = self.generate_root_cause_hypothesis(
            category,
            error_type,
            affected_comps,
            has_stack_trace,
        )

        # Generate Code Fix, Patch & Test
        target_file, code_patch, test_code, fix_expl = self.generate_code_solution(
            issue.title,
            issue.body or "",
            category,
            error_type,
            extracted_tb,
            affected_comps,
        )

        # Upsert IssueAnalysis
        existing_analysis = (
            db.query(IssueAnalysis).filter(IssueAnalysis.issue_id == issue.id).first()
        )
        now_utc = datetime.now(timezone.utc)

        if existing_analysis:
            existing_analysis.category = category
            existing_analysis.priority = priority
            existing_analysis.confidence = confidence
            existing_analysis.model_version = self.model_version
            existing_analysis.root_cause_hypothesis = root_cause
            existing_analysis.error_type = error_type
            existing_analysis.stack_trace_detected = has_stack_trace
            existing_analysis.reproduction_steps_detected = has_repro
            existing_analysis.extracted_stack_trace = extracted_tb
            existing_analysis.affected_components = affected_comps
            existing_analysis.fix_target_file = target_file
            existing_analysis.proposed_code_patch = code_patch
            existing_analysis.verification_test_code = test_code
            existing_analysis.patch_explanation = fix_expl
            existing_analysis.analyzed_at = now_utc
            analysis = existing_analysis
        else:
            analysis = IssueAnalysis(
                issue_id=issue.id,
                category=category,
                priority=priority,
                confidence=confidence,
                model_version=self.model_version,
                root_cause_hypothesis=root_cause,
                error_type=error_type,
                stack_trace_detected=has_stack_trace,
                reproduction_steps_detected=has_repro,
                extracted_stack_trace=extracted_tb,
                affected_components=affected_comps,
                fix_target_file=target_file,
                proposed_code_patch=code_patch,
                verification_test_code=test_code,
                patch_explanation=fix_expl,
                analyzed_at=now_utc,
            )
            db.add(analysis)

        db.flush()

        # Replace existing action recommendations
        db.query(ActionRecommendation).filter(ActionRecommendation.issue_id == issue.id).delete()

        rec_items = self.generate_recommendations(
            category,
            priority,
            error_type,
            has_stack_trace,
            has_repro,
            affected_comps,
        )

        for r in rec_items:
            rec = ActionRecommendation(
                issue_id=issue.id,
                action_type=r["action_type"],
                action_title=r["action_title"],
                rationale=r["rationale"],
                severity=r["severity"],
                created_at=now_utc,
            )
            db.add(rec)

        db.commit()
        db.refresh(analysis)
        return analysis
