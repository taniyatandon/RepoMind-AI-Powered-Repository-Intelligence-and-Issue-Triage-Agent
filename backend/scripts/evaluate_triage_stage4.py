"""Run the isolated Stage 4 triage evaluation corpus (not development fixtures)."""

import json
import re
from pathlib import Path
import sys
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.triage_service import TriageService


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "evaluation" / "triage_stage4_cases.json"
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    case_path = parser.parse_args().cases
    service = TriageService()
    cases = json.loads(case_path.read_text(encoding="utf-8-sig"))
    tp = fp = fn = 0
    category_correct = category_count = 0
    priority_correct = priority_count = 0
    unsupported = []
    reference_mismatches = []
    rec_useful = []
    rationale_records = []

    for case in cases:
        title, body = case["title"], case["body"]
        text = f"{title}\n{body}"
        signals = service.extract_evidence_signals(title, body)
        actual_signals = {key for key, value in signals.items() if value["status"] == "reported"}
        expected_signals = set(case["signals"])
        tp += len(actual_signals & expected_signals)
        fp += len(actual_signals - expected_signals)
        fn += len(expected_signals - actual_signals)
        if actual_signals != expected_signals:
            print(f"  signal mismatch: expected={sorted(expected_signals)} actual={sorted(actual_signals)}")

        error_type = service.extract_error_type(text)
        category, _ = service.classify_category(title, body, case["labels"], bool(error_type), signals)
        if case.get("category") is not None:
            category_count += 1
            category_correct += category == case["category"]
        priority, _ = service.estimate_priority(category, text, bool(error_type), service.extract_stack_trace(text)[0], case["labels"], signals)
        if case.get("priority") is not None:
            priority_count += 1
            priority_correct += priority == case["priority"]
        priority_basis = service.priority_rationale(priority, case["labels"], text, category)

        index_status = case["index_status"]
        evidence = []
        root = service._root_cause_hypothesis(category, error_type, text, evidence, signals)
        recs = service._recommendations(
            category, error_type, service.has_reproduction_steps(body), evidence, text,
            index_status, priority, priority_basis, signals,
        )
        root_paths = re.findall(r"`([^`]+\.(?:py|js|ts|go|rs|java|rb|md|rst|toml|yaml|yml|json))`", root)
        allowed_paths = {item["file_path"] for item in evidence}
        for path in root_paths:
            if path not in allowed_paths:
                unsupported.append((case["case"], f"unmatched source reference: {path}"))
        if not evidence and re.search(r"\b(?:the root cause is|is caused by|confirmed cause|verified cause)\b", root, re.I):
            unsupported.append((case["case"], "definitive causal claim without indexed evidence"))

        for path in root_paths:
            if path not in allowed_paths:
                reference_mismatches.append((case["case"], path))
        rationale_records.append((case["case"], priority_basis))
        rec_text = " ".join(item["action_title"] + " " + item["rationale"] for item in recs)
        # A recommendation is counted as context-aware if it addresses the manually reviewed focus
        # at the issue-concept level, without requiring a fixed generated sentence.
        focus_tokens = [token.lower() for token in re.findall(r"[a-zA-Z]{5,}", case["recommendation_focus"])]
        overlap = sum(token in rec_text.lower() for token in focus_tokens) / max(len(focus_tokens), 1)
        rec_useful.append((case["case"], overlap >= 0.18, overlap, rec_text))

        print(f"[{case['case']}] category={category} expected={case.get('category')} priority={priority} expected={case.get('priority')}")
        print(f"  root: {root}")
        print(f"  priority rationale: {priority_basis}")
        print(f"  recommendation: {rec_text}")

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    print(f"\n=== Stage 4 summary: {case_path.name} ===")
    print(f"cases={len(cases)}; extraction TP={tp} FP={fp} FN={fn}; micro_precision={precision:.3f}; micro_recall={recall:.3f}; micro_f1={f1:.3f}")
    print(f"classification={category_correct}/{category_count} ({category_correct/category_count:.3f})")
    print(f"priority={priority_correct}/{priority_count} ({priority_correct/priority_count:.3f})")
    print(f"recommendation concept-overlap rubric={sum(x[1] for x in rec_useful)}/{len(rec_useful)} (exploratory, not validated)")
    print(f"unsupported claim/source-reference flags={len(unsupported)}; details={unsupported}")
    print(f"source-reference mismatches={len(reference_mismatches)}; details={reference_mismatches}")
    print("Priority rationales are printed above for manual evidence-support review.")


if __name__ == "__main__":
    main()
