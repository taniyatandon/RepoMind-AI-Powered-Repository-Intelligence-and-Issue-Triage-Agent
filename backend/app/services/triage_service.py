from datetime import datetime, timezone
import hashlib
import json
import re
import unicodedata
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.action_recommendation import ActionRecommendation
from app.models.code_chunk import CodeChunk
from app.models.code_index_status import CodeIndexStatus
from app.models.issue import Issue
from app.models.issue_analysis import IssueAnalysis
from app.models.repository import Repository


FILE_PATH_PATTERN = r"(?<![\w.-])(?:[\w.-]+/)*[\w.-]+\.(?:py|js|ts|jsx|tsx|json|yml|yaml|sql|go|rs|c|cpp|h)(?![\w.-])"
EXCEPTION_LINE_PATTERN = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning|Fault))\s*:",
    re.MULTILINE,
)
MISSING_ATTRIBUTE_PATTERN = re.compile(
    r"module\s+([\w.]+)\s+has no attribute\s+['\"]?([\w]+)", re.IGNORECASE
)
MARKDOWN_SECTION_PATTERN = re.compile(
    r"(?m)^\s*(?:#{1,6}\s+(.+?)\s*|(?:\*\*)?([A-Za-z][^:\n*]{1,80}?)(?:\*\*)?:\s*)$"
)
TRACEBACK_FRAME_PATTERN = re.compile(
    r'(?:^\s*File\s+["\'][^"\']+["\'],\s*line\s+\d+'
    r'|^\s*\S+\.go:\d+\b'
    r'|^\s*at\s+[^\n]+?(?:\([^\n]*:\d+:\d+\)|:\d+:\d+)\s*$'
    r'|^\s*\w+(?:\.\w+)+\([^\n]*\)\s*$)', re.I | re.M,
)
SIGNAL_NAMES = (
    "environment", "configuration", "code_examples", "symptoms",
    "observed_results", "expected_behavior", "reproduction_steps",
    "executable_reproductions", "stack_traces", "logs",
)


class TriageService:
    MODEL_VERSION = "repomind-triage-v1.4-evidence"

    @staticmethod
    def issue_content_digest(title: str | None, body: str | None) -> str:
        """Return a stable digest for the title and body used by issue triage."""
        normalized = [
            unicodedata.normalize("NFC", (value or "").replace("\r\n", "\n").replace("\r", "\n"))
            for value in (title, body)
        ]
        content = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def __init__(self, model_version: str = MODEL_VERSION):
        self.model_version = model_version

    def extract_stack_trace(self, text: str) -> tuple[bool, str | None]:
        for block, _language in self._fenced_blocks(text):
            if TRACEBACK_FRAME_PATTERN.search(block):
                return True, block.strip()
        python_trace = re.search(
            r"Traceback \(most recent call last\):[\s\S]*?"
            r"^[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning|Fault):[^\n]*",
            text, re.M,
        )
        if python_trace and TRACEBACK_FRAME_PATTERN.search(python_trace.group(0)):
            return True, python_trace.group(0).strip()
        if TRACEBACK_FRAME_PATTERN.search(text):
            lines = text.splitlines()
            frame_indexes = [i for i, line in enumerate(lines) if TRACEBACK_FRAME_PATTERN.match(line)]
            if frame_indexes:
                start = frame_indexes[0]
                end = frame_indexes[-1] + 1
                while end < len(lines) and (EXCEPTION_LINE_PATTERN.match(lines[end]) or not lines[end].strip()):
                    end += 1
                while start > 0 and ("traceback" in lines[start - 1].lower() or not lines[start - 1].strip()):
                    start -= 1
                return True, "\n".join(lines[start:end]).strip()
        return False, None

    def extract_error_type(self, text: str) -> str | None:
        match = EXCEPTION_LINE_PATTERN.search(text)
        if match:
            return match.group(1).split(".")[-1]
        http_error = re.search(r"\bHTTP\s+([45]\d\d)\b", text, re.IGNORECASE)
        return f"HTTP {http_error.group(1)}" if http_error else None

    def extract_mentioned_paths(self, text: str) -> list[str]:
        return list(dict.fromkeys(re.findall(FILE_PATH_PATTERN, text)))[:12]

    def has_reproduction_steps(self, text: str) -> bool:
        return self.extract_evidence_signals("", text)["reproduction_steps"]["status"] == "reported"

    @staticmethod
    def _fenced_blocks(text: str) -> list[tuple[str, str]]:
        blocks = []
        for match in re.finditer(r"```([^\s`]*)[^\n]*\n([\s\S]*?)```|~~~([^\s~]*)[^\n]*\n([\s\S]*?)~~~", text or ""):
            blocks.append((match.group(2) if match.group(1) is not None else match.group(4),
                           (match.group(1) if match.group(1) is not None else match.group(3) or "").lower()))
        return blocks

    @staticmethod
    def _normal_heading(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    @staticmethod
    def _append_signal(signals: dict[str, dict[str, Any]], key: str, value: str) -> None:
        value = value.strip()
        if value and value not in signals[key]["excerpts"]:
            signals[key]["excerpts"].append(value[:1200])
            signals[key]["status"] = "reported"

    def extract_evidence_signals(self, title: str, body: str) -> dict[str, dict[str, Any]]:
        """Extract issue evidence with explicit status; preserve excerpts rather than infer causes."""
        signals = {name: {"status": "not_found", "excerpts": []} for name in SIGNAL_NAMES}
        text = f"{title or ''}\n{body or ''}"
        lines = (body or "").splitlines(keepends=True)
        fences = list(re.finditer(r"```([^\s`]*)[^\n]*\n([\s\S]*?)```|~~~([^\s~]*)[^\n]*\n([\s\S]*?)~~~", body or ""))
        fenced_spans = [(m.start(), m.end()) for m in fences]
        fence_values = [(m.group(2) if m.group(1) is not None else m.group(4),
                         (m.group(1) if m.group(1) is not None else m.group(3) or "").lower()) for m in fences]

        headings = list(MARKDOWN_SECTION_PATTERN.finditer(body or ""))
        sections = []
        for i, heading in enumerate(headings):
            end = headings[i + 1].start() if i + 1 < len(headings) else len(body or "")
            sections.append((self._normal_heading(heading.group(1) or heading.group(2)), heading.end(), end))

        def heading_for(position: int) -> str:
            for heading, start, end in sections:
                if start <= position < end:
                    return heading
            return ""

        def target_for_heading(heading: str) -> str | None:
            if re.search(r"\b(expected|desired|should|intended|acceptance criteria)\b", heading):
                return "expected_behavior"
            if re.search(r"\b(repro|reproduce|reproduction|steps|procedure)\b", heading):
                return "reproduction_steps"
            if re.search(r"\b(environment|system|platform|runtime|versions?|dependencies|setup)\b", heading):
                return "environment"
            if re.search(r"\b(config|configuration|settings?|options?|flags?)\b", heading):
                return "configuration"
            if re.search(r"\b(actual|observed|result|output|current behavior|what i see|what i observe|what happens)\b", heading):
                return "observed_results"
            if re.search(r"\b(symptom|problem|error|failure|what happened|what went wrong)\b", heading):
                return "symptoms"
            if re.search(r"\b(logs?|console|diagnostic output)\b", heading):
                return "logs"
            if re.search(r"\b(code|example|sample|snippet)\b", heading):
                return "code_examples"
            return None

        for match, (value, language) in zip(fences, fence_values):
            if not value.strip():
                continue
            heading = heading_for(match.start())
            if language in {"env", "dotenv", "yaml", "yml", "json", "toml", "ini", "properties"}:
                self._append_signal(signals, "configuration", value)
            elif language not in {"text", "txt", "log", "logs", "console", "trace", "traceback", "output", "shelloutput"}:
                self._append_signal(signals, "code_examples", value)
            if re.search(r"\b(repro|reproduce|reproduction|steps)\b", heading) or (language in {"bash", "sh", "shell", "console"} and re.search(r"\b(run|install|curl|python|npm|pytest|uv)\b", value, re.I)):
                self._append_signal(signals, "executable_reproductions", value)
            if re.search(r"\b(log|console|trace|output)\b", heading) or re.search(r"(?m)^\s*(?:\d{4}-\d\d-\d\d[T ]|(?:DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL)\b)", value):
                self._append_signal(signals, "logs", value)
            if TRACEBACK_FRAME_PATTERN.search(value) or re.search(r"(?m)^\s*goroutine\s+\d+", value):
                self._append_signal(signals, "stack_traces", value)
            if EXCEPTION_LINE_PATTERN.search(value) or re.search(r"(?im)^\s*panic\s*:", value):
                self._append_signal(signals, "symptoms", value)

        # Capture non-fenced lines, using headings as hints and content patterns as fallback.
        offset = 0
        for raw_line in lines:
            line_start, offset = offset, offset + len(raw_line)
            line = raw_line.rstrip("\r\n")
            if any(start <= line_start < end for start, end in fenced_spans):
                continue
            heading = heading_for(line_start)
            clean = re.sub(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", line).strip()
            if not clean or clean.startswith((">", "#")):
                continue
            # Sentence and explicit field-boundary splitting keeps one paragraph from being
            # copied wholesale into environment, observed, expected, and symptom signals.
            fragments = re.split(
                r"(?<=[.!?])\s+(?=[A-Z0-9])|\s+(?=(?:actual(?:ly)?(?: output| result)?|observed(?: result)?|expected(?: behavior| result| output)?|reproduce by\b|to reproduce|steps to reproduce|environment)\s*[:=-]?)",
                clean,
            )
            for fragment in fragments:
                clean = fragment.strip()
                if not clean or clean.startswith((">", "#")):
                    continue
                target = target_for_heading(heading)
                field_match = re.match(r"^(expected(?: behavior| result| output)?|observed(?: result)?|actual(?: output| result)?|result(?:s)?|environment|configuration|steps to reproduce|reproduce by|to reproduce)\s*(?:[:=-]\s*|\s+)", clean, re.I)
                if field_match:
                    field_name = self._normal_heading(field_match.group(1))
                    if field_name.startswith("expected"):
                        target = "expected_behavior"
                    elif field_name.startswith(("observed", "actual", "result")):
                        target = "observed_results"
                    elif field_name == "environment":
                        target = "environment"
                    elif field_name == "configuration":
                        target = "configuration"
                    else:
                        target = "reproduction_steps"
                versionish = bool(re.search(r"\b(?:[\w.+-]+\s+){0,3}v?\d+\.\d+(?:\.\d+){0,2}\b|\bversion\s+v?\d+(?:\.\d+){0,3}\b|\b(?:runtime|platform|operating system)\s*[:=]", clean, re.I))
                configish = bool(
                    re.search(r"\b[A-Z][A-Z0-9_]{2,}\s*=|(?:^|\s)--[\w-]+(?:=|\s)|:\s*['\"\w/-]+\s*$", clean)
                    or re.search(r"\b(?:env(?:ironment)? vars?|environment variables?)\b.{0,50}\b(?:set|configured|provided)\b", clean, re.I)
                )
                if target and target != "reproduction_steps":
                    self._append_signal(signals, target, clean)
                inline_code_example = re.search(r"`[^`]*(?:=|\(|\)|\{|\}|;|\b(?:python\s+-|npm\s|curl\s|pytest\s|import\s|return\s))[^`]*`", fragment, re.I)
                if re.search(r"^ {4,}\S|^(?:\$\s*)?(?:import\s+(?!the\b|a\b|an\b|package\b|module\b)[A-Za-z_]|from\s+\S+\s+import|def\s|class\s|function\s|const\s|let\s|var\s|async\s|await\s|return\s|print\s*\(|curl\s|python\s+-|npm\s+|pytest\s)", fragment, re.I) or inline_code_example:
                    self._append_signal(signals, "code_examples", clean)
                if versionish or re.search(r"\b(?:OS|operating system|runtime|platform|dependency|package version)\s*[:=]", clean, re.I):
                    self._append_signal(signals, "environment", clean)
                if configish:
                    self._append_signal(signals, "configuration", clean)
                symptom_pattern = r"\b(?:fails?|failed|crashes?|throws?|raises?|unavailable|cannot|can't|unable to|blocked|affected|wrong|incorrect|mismatch|off by|stops?|ceased|zero[- ]byte|empty (?:table|response|result|output)|returns?\s+(?:an?\s+)?(?:error|exception|\d{3}|http\s+\d{3})|error|exception|time(?:s|d)?\s*out|timeout|hangs?|regress(?:ion|ed)|unauthori[sz]ed\s+(?:access|reads?|writes?)|(?:data|record)s?\s+(?:is\s+)?exposed|panic)\b|\b[A-Za-z_][\w.]*(?:Error|Exception|Fault)\s*:"
                is_reproduction_text = bool(re.match(r"^(?:to reproduce|reproduce by|steps to reproduce)\s*(?:[:=-]\s*|\s+)", clean, re.I))
                if is_reproduction_text and re.search(r"\b(run|install|set|creat\w*|start|send\w*|open|click|call|configure|build|execut\w*|load|restart|navigate|curl|python|npm|pytest)\b", clean, re.I):
                    self._append_signal(signals, "reproduction_steps", clean)
                if not is_reproduction_text and self._has_affirmed_match(clean, symptom_pattern):
                    self._append_signal(signals, "symptoms", clean)
                if target != "expected_behavior" and re.search(r"\b(?:should|must|instead of|rather than|want(?:ed)? to|would like to|please add|request(?:ed)? to)\b", clean, re.I):
                    self._append_signal(signals, "expected_behavior", clean)
                observed_cue = self._has_affirmed_match(clean, r"\b(?:received|visible in|confirms?|shows?|remains?|stays?|succeeds?|works?|successful|arrives?|appear(?:s)?|peaks? at|response body|returns?\s+(?:http\s+)?\d{3}|returns?\s+(?:the|an?)\s+(?:wrong|incorrect|intermediate))\b")
                observed_label = bool(re.match(r"^(?:observed|actual(?:ly)?(?: result)?|result(?:s)?)\s*[:=-]", clean, re.I))
                if not is_reproduction_text and (observed_cue or observed_label):
                    self._append_signal(signals, "observed_results", clean)
                if target == "observed_results":
                    # An "instead of" phrase can describe actual output; the field heading
                    # is stronger than the lexical cue when assigning this sentence.
                    signals["expected_behavior"]["excerpts"] = [item for item in signals["expected_behavior"]["excerpts"] if item != clean]
                    if not signals["expected_behavior"]["excerpts"] and signals["expected_behavior"]["status"] == "reported":
                        signals["expected_behavior"]["status"] = "not_found"
                if target == "expected_behavior":
                    signals["observed_results"]["excerpts"] = [item for item in signals["observed_results"]["excerpts"] if item != clean]
                    if not signals["observed_results"]["excerpts"] and signals["observed_results"]["status"] == "reported":
                        signals["observed_results"]["status"] = "not_found"
                if TRACEBACK_FRAME_PATTERN.match(clean) or re.match(r"^\s*(?:goroutine\s+\d+|\S+\.go:\d+)\b", clean):
                    self._append_signal(signals, "stack_traces", clean)
                if re.match(r"^\s*(?:\d{4}-\d\d-\d\d[T ]|(?:DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|PANIC)\b)", clean, re.I):
                    self._append_signal(signals, "logs", clean)
                # Numbered or imperative actions count as steps, not arbitrary section prose.
                numbered = bool(re.match(r"^\s*\d+[.)]\s+", line)) and (
                    re.search(r"\b(repro|reproduce|steps|procedure)\b", heading)
                    or bool(re.match(r"^(?:run|install|set|create|start|send|open|click|call|configure|build|execute|load|restart|navigate|then|first|next)\b", clean, re.I))
                )
                imperative = bool(re.match(r"^(?:run|install|set|create|start|send|open|click|call|configure|build|execute|load|restart|navigate|then|first|next)\b", clean, re.I))
                if numbered or (imperative and (re.search(r"\b(repro|reproduce|reproduction|steps|procedure|then|after|before)\b", heading) or re.match(r"^(?:first|next|then)\b", clean, re.I))):
                    self._append_signal(signals, "reproduction_steps", clean)
                elif re.match(r"^(?:to reproduce|reproduce by|steps to reproduce)\s*(?:[:=-]\s*|\s+)", clean, re.I) and re.search(r"\b(run|install|set|creat\w*|start|send\w*|open|click|call|configure|build|execut\w*|load|restart|navigate|curl|python|npm|pytest)\b", clean, re.I):
                    self._append_signal(signals, "reproduction_steps", clean)

        # A concise title may contain the only direct description of the failure.
        title_prose = self._assessment_prose(title or "")
        title_symptom_pattern = r"\b(?:fails?|failed|crashes?|throws?|raises?|unavailable|cannot|can't|unable to|blocked|wrong|incorrect|mismatch|off by|regress(?:ion|ed)|unauthori[sz]ed\s+(?:access|read|write)|(?:data|record)s?\s+(?:is\s+)?exposed|returns?\s+(?:an?\s+)?(?:error|exception|\d{3}))\b|\b[A-Za-z_][\w.]*(?:Error|Exception|Fault)\s*:"
        if self._has_affirmed_match(title.strip(), title_symptom_pattern):
            self._append_signal(signals, "symptoms", title.strip())
        # Explicit absence is distinct from no mention; only report absence when issue text says so.
        absence_terms = {
            "environment": r"runtime|environment|version|platform|dependencies",
            "configuration": r"configuration|config|settings",
            "code_examples": r"(?:code|source)\s+(?:example|sample|snippet)|example|sample|snippet",
            "symptoms": r"error|failure|crash|symptom",
            "observed_results": r"(?:observed|actual|reported)\s+(?:result|behavior|output)|result|output",
            "expected_behavior": r"expected behavior|expected result",
            "reproduction_steps": r"reproduction steps|steps to reproduce|reproducer",
            "executable_reproductions": r"executable|runnable|minimal reproduction|test",
            "stack_traces": r"stack trace|traceback|stack frames",
            "logs": r"logs?|console output|diagnostic output",
        }
        flattened = re.sub(r"[_-]+", " ", text.lower())
        for key, terms in absence_terms.items():
            absent = re.search(rf"\b(?:no|without|not provided|not available|not specified|not captured)\b.{{0,50}}\b(?:{terms})\b", flattened, re.I)
            if absent:
                signals[key]["excerpts"] = [
                    excerpt for excerpt in signals[key]["excerpts"]
                    if not re.search(rf"\b(?:{terms})\b", excerpt, re.I)
                ]
            if absent and not signals[key]["excerpts"]:
                signals[key]["status"] = "explicitly_absent"
        return signals

    def _reported_context_facts(self, body: str) -> list[dict[str, str]]:
        signals = self.extract_evidence_signals("", body)
        labels = {
            "environment": "Environment and versions", "configuration": "Configuration",
            "code_examples": "Code example", "symptoms": "Reported symptom",
            "observed_results": "Observed result", "expected_behavior": "Expected behavior",
            "reproduction_steps": "Reproduction step", "executable_reproductions": "Executable reproduction",
            "stack_traces": "Stack trace", "logs": "Log output",
        }
        facts = [
            {"kind": f"evidence_{key}", "label": labels[key], "value": value}
            for key, signal in signals.items() for value in signal["excerpts"]
        ]
        facts.extend({
            "kind": f"evidence_status_{key}", "label": f"{label} signal status",
            "value": {"not_found": "Not found in issue text", "explicitly_absent": "Explicitly reported absent", "reported": "Reported"}[signals[key]["status"]],
        } for key, label in labels.items())
        if signals["reproduction_steps"]["status"] != "reported" and signals["executable_reproductions"]["status"] != "reported":
            facts.append({"kind": "reproduction_limit", "label": "Minimal reproduction", "value": "No reproduction steps or executable reproduction were found; this is distinct from missing environment or symptom information."})
        return facts

    @staticmethod
    def _label_names(labels: list[Any]) -> set[str]:
        names: set[str] = set()
        for label in labels or []:
            raw = label.get("name", "") if isinstance(label, dict) else label
            if isinstance(raw, str):
                normalized = re.sub(r"[_-]+", " ", raw.strip().lower())
                names.add(re.sub(r"\s+", " ", normalized))
        return names

    def classify_category(
        self, title: str, body: str, labels: list[Any], has_error: bool,
        evidence_signals: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[str, float]:
        prose = self._assessment_prose(f"{title}\n{body}")
        scores = {kind: 0.0 for kind in ("bug", "feature_request", "improvement", "documentation", "question")}
        label_map = {
            "bug": {"bug", "bug report", "defect", "fault", "type bug", "type: bug", "kind bug", "kind: bug"},
            "feature_request": {"enhancement", "feature", "feature request", "type feature", "type: feature", "type enhancement", "type: enhancement"},
            "improvement": {"improvement", "performance", "optimization", "refactor"},
            "documentation": {"documentation", "docs", "type documentation", "type: documentation"},
            "question": {"question", "support", "type question", "type: question"},
        }
        names = self._label_names(labels)
        label_categories = {kind for kind, aliases in label_map.items() if names & aliases}
        if len(label_categories) == 1:
            scores[next(iter(label_categories))] += 0.8

        # Prefer evidence of the issue's requested change or behavior over label-only matches.
        for pattern, kind, weight in (
            (r"\b(?:bug|defect|regress(?:ion|ed)|crash(?:es|ed)?|fails?|failure|throws?|raises?|unavailable|cannot|can't|unable to|blocked|wrong|incorrect|mismatch|unauthori[sz]ed (?:access|reads?|writes?)|data (?:is )?exposed)\b|\bdoes not work\b|\bunexpected behavior\b", "bug", 1.55),
            (r"\b(?:feature request|request(?:ing)? (?:to )?add|please add|would like to|could you add|support for|please support|support selecting|allow (?:users? to )?(?:select|choose|set|configure|include)|provide an? (?:option|setting|parameter))\b", "feature_request", 2.6),
            (r"\b(?:refactor|optimi[sz]e|improve|reduce|simplify|lower|decrease)\b.{0,60}\b(?:performance|latency|memory|cpu|allocations?|complexity|cost|throughput)\b|\b(?:performance|latency|memory|cpu|allocations?|complexity|cost|throughput)\b.{0,60}\b(?:refactor|optimi[sz]e|improve|reduce|simplify|lower|decrease)\b", "improvement", 3.0),
            (r"\b(?:documentation|docs|readme|guide|manual|reference|tutorial|instructions?|document(?:ation)?)\b[\s\S]{0,80}\b(?:missing|omit(?:s|ted)?|skip(?:s|ped)?|unclear|incorrect|outdated|typo|document(?:s|ed|ing)?|clarify|add(?:s|ed|ing)?|update|explain)\b|\b(?:missing|omit(?:s|ted)?|skip(?:s|ped)?|unclear|incorrect|outdated|typo|clarify|update|add(?:s|ed|ing)?|document(?:s|ed|ing)?)\b[\s\S]{0,80}\b(?:documentation|docs|readme|guide|manual|reference|tutorial|instructions?|document(?:ation)?)\b|\bdocument\s+(?:the|how|when|what|whether|a|an)\b", "documentation", 2.6),
            (r"\b(?:how can i|how do i|what is the way to|is it possible|could (?:someone|you) explain|asking whether|whether .{0,60} is expected)\b", "question", 1.35),
        ):
            if self._has_affirmed_match(prose, pattern):
                scores[kind] += weight
        has_behavior_gap = bool(
            evidence_signals
            and evidence_signals.get("expected_behavior", {}).get("status") == "reported"
            and evidence_signals.get("observed_results", {}).get("status") == "reported"
        )
        ambiguous_conflict = (
            re.search(r"\b(?:unclear|uncertain|conflicting|contradictory|inconsistent|cannot tell whether|can't tell whether|not sure whether|do not know whether|don't know whether)\b", prose)
            and re.search(r"\b(?:succeeds?|works?|success(?:ful(?:ly)?)?|completes?)\b", prose)
            and (re.search(r"\b(?:fails?|failure|error|exception|crashes?|does not work)\b", prose)
                 or re.search(r"\b[A-Z][A-Za-z0-9_.]*(?:Error|Exception|Fault)\b", f"{title}\n{body}"))
        )
        if ambiguous_conflict:
            return "unknown", 0.50
        if not has_behavior_gap and re.search(r"\b(?:what|why|how|when|where|which|who|can|could|would|is|are|do|does|will)\b[^\n?]{0,140}\?", prose):
            scores["question"] += 1.2

        # An asserted difference between actual and expected behavior is strong bug evidence.
        if evidence_signals:
            reported = lambda key: evidence_signals.get(key, {}).get("status") == "reported"
            if reported("symptoms") and (reported("observed_results") or has_error):
                scores["bug"] += 1.0
            if reported("expected_behavior") and reported("observed_results"):
                scores["bug"] += 1.5
            if reported("reproduction_steps") and reported("symptoms"):
                scores["bug"] += 0.3
        elif has_error:
            scores["bug"] += 1.1

        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        best_kind, best_score = ranked[0]
        runner_up = ranked[1][1]
        if best_score < 1.0 or best_score - runner_up < 0.25:
            return "unknown", 0.50
        return best_kind, min(0.90, 0.55 + (best_score - runner_up) * 0.10)

    @classmethod
    def _assessment_prose(cls, text: str) -> str:
        prose = cls._prose(text).lower()
        prose = re.sub(r"(?m)^\s*>.*$", " ", prose)
        prose = re.sub(r'"[^"\n]*"', " ", prose)
        prose = re.sub(r"\u2018[^\u2019\n]*\u2019|\u201c[^\u201d\n]*\u201d", " ", prose)
        prose = re.sub(r"[\"“][^\"”]*[\"”]", " ", prose)
        prose = re.sub(r"(?<!\w)'[^'\n]{2,}'(?!\w)", " ", prose)
        return prose

    @staticmethod
    def _has_affirmed_match(text: str, pattern: str) -> bool:
        negation = re.compile(r"\b(?:not|no|never|without|isn['’]t|doesn['’]t|didn['’]t|cannot|can['’]t|won['’]t|isn['’]t|isn't|doesn't|didn't|can't|won't)\b", re.I)
        for match in re.finditer(pattern, text, re.I):
            if re.search(r"\bcannot\s+tell\s+whether\b", text[max(0, match.start() - 8):match.end() + 20], re.I):
                continue
            before = text[max(0, match.start() - 55):match.start()]
            after = text[match.end():match.end() + 45]
            # Treat a nearby negator as cancellation, but permit contrastive constructions.
            prefix = re.split(r"[.!?;\n]", before)[-1]
            prefix = re.split(r"\b(?:but|however|although|except)\b", prefix)[-1]
            suffix = re.split(r"\b(?:but|however|although|except)\b", after)[0]
            trailing_negation = re.match(r"\s*(?:(?:is|are|was|were|does|do|did|has|have|will)\s+)?(?:not|never|no longer)\b", suffix)
            scoped_negation = re.search(r"\b(?:not|no|never|without|isn['â€™]t|doesn['â€™]t|didn['â€™]t|cannot|can['â€™]t|won['â€™]t|isn't|doesn't|didn't|can't|won't)\b(?:\W+\w+){0,6}\W*$", prefix, re.I)
            if (scoped_negation and not re.search(r"\bnot only\b", prefix)) or trailing_negation:
                continue
            return True
        return False

    @staticmethod
    def _prose(text: str) -> str:
        text = re.sub(r"```[\s\S]*?```", " ", text)
        text = re.sub(r"`[^`]*`", " ", text)
        text = re.sub(r"(?m)^\s*>.*$", " ", text)
        return text

    def estimate_priority(
        self, category: str, text: str, has_error: bool, has_stack_trace: bool,
        labels: list[Any] | None = None,
        evidence_signals: dict[str, dict[str, Any]] | None = None,
    ) -> tuple[str, float]:
        prose = self._assessment_prose(text)
        labels = labels or []
        label_priority = self._priority_label(labels)
        severe = self._has_affirmed_match(
            prose, r"\b(?:unauthori[sz]ed (?:access|reads?|writes?)|security (?:vulnerability|breach|exposure|bypass)|permanent data loss|irrecoverable data|data corruption|(?:customer|tenant|account) data (?:is )?exposed|service[- ]wide outage)\b"
        )
        urgent = self._has_affirmed_match(
            prose, r"\b(?:production outage|service unavailable|prevents? (?:deployment|release|startup)|blocks? (?:deployment|release)|release[- ]blocking|production is down)\b"
        )
        broad_scope = self._has_affirmed_match(
            prose, r"\b(?:all|every|most|many|multiple|widespread|organization[- ]wide|service[- ]wide)\s+(?:(?:[\w-]+)\s+){0,2}(?:users?|customers?|tenants?|accounts?|workspaces?|organizations?|regions?|requests?|workflows?|services?|instances?)(?:['’]s)?\b|\b(?:users?|customers?|workspaces?)\s+(?:across the board|are all affected)\b|\b(?:across|throughout)\s+(?:all|every|multiple)\s+(?:tenants?|accounts?|workspaces?|organizations?|regions?)\b"
        )
        constrained = self._has_affirmed_match(
            prose, r"\b(?:only|single|one)\s+(?:user|customer|tenant|account|admin(?:istrator)?|request|machine|environment)\b|\b(?:workaround exists|workaround available|cosmetic only|minor inconvenience)\b"
        )
        functional_impact = self._has_affirmed_match(
            prose, r"\b(?:cannot|can't|unable to|fails?(?:\s+(?:to|when|on|under|for))?|prevents? .*? from|blocks? .*? from|blocked|crashes?|data (?:loss|corruption)|unavailable|time(?:s|d)? out|timeout|degraded|incorrect result|unauthori[sz]ed\s+(?:access|read|write))\b"
        )
        urgency = self._has_affirmed_match(prose, r"\b(?:urgent|time[- ]critical|deadline|immediate|blocking)\b")

        if evidence_signals and evidence_signals.get("symptoms", {}).get("status") == "reported" and evidence_signals.get("observed_results", {}).get("status") == "reported":
            functional_impact = True
        if severe and (broad_scope or urgent or functional_impact):
            priority, score = "P0_CRITICAL", 0.88
        elif urgent:
            priority, score = "P1_HIGH", 0.82
        elif broad_scope and functional_impact:
            priority, score = "P1_HIGH", 0.78
        elif functional_impact and constrained:
            priority, score = "P2_MEDIUM", 0.68
        elif urgency and functional_impact:
            priority, score = "P2_MEDIUM", 0.66
        else:
            priority, score = "P3_LOW", 0.55

        # Labels are corroborating metadata. Conflicting labels or contradictory report impact
        # never override evidence; a solitary label may supply a provisional fallback.
        report_denies_impact = bool(re.search(
            r"\b(?:no|not|without|never)\b.{0,50}\b(?:outage|users?(?:\s+are)?\s+(?:affected|impacted|blocked)|customers?(?:\s+are)?\s+(?:affected|impacted|blocked)|blocked|data loss|security (?:breach|vulnerability)|service unavailable|release blocker)\b|\b(?:production|service)\b.{0,30}\b(?:not|never|no longer)\b.{0,20}\b(?:down|unavailable|in outage)\b",
            prose,
        ))
        if label_priority and not (severe or urgent or broad_scope or functional_impact or constrained or report_denies_impact):
            priority, score = label_priority, 0.58
        return priority, score

    @staticmethod
    def _has_unnegated_phrase(text: str, phrases: tuple[str, ...]) -> bool:
        return any(
            re.search(rf"(?<!\bnot )(?<!\bno )(?<!\bwithout ){re.escape(phrase)}", text)
            for phrase in phrases
        )

    @staticmethod
    def _priority_label(labels: list[Any]) -> str | None:
        names = TriageService._label_names(labels)
        found = set()
        for name in names:
            name = re.sub(r"[:=_-]+", " ", name).strip()
            match = re.fullmatch(r"p([0-3])|(?:priority|severity)\s+(?:p([0-3])|(critical|high|medium|low))|critical|high|medium|low", name)
            if match:
                raw = next((value for value in match.groups() if value is not None), None)
                raw = raw or name
                found.add({"0": "P0_CRITICAL", "1": "P1_HIGH", "2": "P2_MEDIUM", "3": "P3_LOW",
                           "critical": "P0_CRITICAL", "high": "P1_HIGH", "medium": "P2_MEDIUM", "low": "P3_LOW"}[raw])
        return next(iter(found)) if len(found) == 1 else None

    @classmethod
    def priority_rationale(cls, priority: str, labels: list[Any], text: str = "", category: str | None = None) -> str:
        prose = cls._assessment_prose(text)
        reasons = []
        if cls._has_affirmed_match(prose, r"\b(?:unauthori[sz]ed (?:access|reads?|writes?)|security (?:vulnerability|breach|exposure|bypass)|permanent data loss|irrecoverable data|data corruption|(?:customer|tenant|account) data (?:is )?exposed)\b"):
            reasons.append("the report states a security or data-integrity impact")
        if cls._has_affirmed_match(prose, r"\b(?:production outage|service unavailable|prevents? (?:deployment|release|startup)|blocks? (?:deployment|release)|production is down)\b"):
            reasons.append("the report describes an outage or a deployment/release/startup blocker")
        if cls._has_affirmed_match(prose, r"\b(?:all|every|most|many|multiple|widespread|organization[- ]wide|service[- ]wide)\s+(?:(?:[\w-]+)\s+){0,2}(?:users?|customers?|tenants?|accounts?|workspaces?|organizations?|regions?|requests?|workflows?|services?|instances?)(?:['’]s)?\b|\b(?:users?|customers?|workspaces?)\s+(?:across the board|are all affected)\b|\b(?:across|throughout)\s+(?:all|every|multiple)\s+(?:tenants?|accounts?|workspaces?|organizations?|regions?)\b"):
            reasons.append("the reported scope extends beyond an isolated case")
        if category not in {"documentation", "feature_request", "question"} and cls._has_affirmed_match(prose, r"\b(?:cannot|can't|unable to|fails?(?:\s+(?:to|when|on|under|for))?|crashes?|unavailable|time(?:s|d)? out|timeout|degraded|incorrect result)\b"):
            reasons.append("the report describes blocked or failed functionality")
        if cls._has_affirmed_match(prose, r"\b(?:only\s+(?:one|a single)\s+|single\s+|one\s+)(?:user|customer|tenant|account|admin(?:istrator)?|request|machine|environment)\b"):
            reasons.append("the stated scope is limited to one affected user, customer, request, or environment")
        if cls._has_affirmed_match(prose, r"\bworkaround (?:exists|is available|available)\b"):
            reasons.append("the report states that a workaround is available")
        if priority in {"P0_CRITICAL", "P1_HIGH", "P2_MEDIUM"} and reasons:
            return f"{priority} is provisional based on reported impact: " + "; ".join(reasons) + "."
        label_priority = cls._priority_label(labels)
        if label_priority == priority:
            return f"{priority} follows a single GitHub priority label; the issue text does not provide enough impact details to verify severity."
        if reasons:
            return "Priority remains provisional; reported impact evidence: " + "; ".join(reasons) + "."
        return "P3_LOW is provisional because the issue text does not establish impact scope, urgency, or affected users."

    def _repository_evidence(
        self, issue: Issue, db: Session, text: str, error_type: str | None,
        stack_trace: str | None,
    ) -> list[dict[str, Any]]:
        repo = db.query(Repository).filter(Repository.id == issue.repository_id).first()
        if not repo:
            return []

        paths = self.extract_mentioned_paths(stack_trace or "")

        identifiers: set[str] = set()
        missing_attr = MISSING_ATTRIBUTE_PATTERN.search(text)
        if missing_attr:
            identifiers.update(missing_attr.groups())
        elif error_type and not error_type.startswith("HTTP "):
            identifiers.add(error_type)

        conditions = []
        if paths:
            conditions.append(CodeChunk.file_path.in_(paths))
        for token in sorted(identifiers)[:12]:
            if len(token) >= 4:
                conditions.append(CodeChunk.content.ilike(f"%{token}%"))
        if not conditions:
            return []

        chunks = (
            db.query(CodeChunk)
            .filter(CodeChunk.repository_id == issue.repository_id, or_(*conditions))
            .limit(200)
            .all()
        )
        ranked: list[tuple[int, CodeChunk, list[str]]] = []
        for chunk in chunks:
            matched = [term for term in identifiers if term.lower() in chunk.content.lower()]
            path_match = chunk.file_path in paths
            if not matched and not path_match:
                continue
            ranked.append((len(matched) + (2 if path_match else 0), chunk, matched))
        ranked.sort(key=lambda item: (-item[0], item[1].file_path, item[1].start_line))

        evidence: list[dict[str, Any]] = []
        seen: set[tuple[str, int, int]] = set()
        for _, chunk, matched in ranked:
            key = (chunk.file_path, chunk.start_line, chunk.end_line)
            if key in seen:
                continue
            seen.add(key)
            evidence.append({
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "matched_terms": matched,
                "snippet": chunk.content[:900],
                "commit_sha": chunk.commit_sha,
            })
            if len(evidence) >= 5:
                break
        return evidence

    def _issue_facts(
        self, issue: Issue, error_type: str | None, has_stack_trace: bool,
        has_repro: bool,
    ) -> list[dict[str, str]]:
        facts = [{
            "kind": "github_issue",
            "label": f"Issue #{issue.issue_number}",
            "value": issue.title,
            "url": issue.html_url,
        }]
        if issue.repository:
            facts.append({
                "kind": "github_repository",
                "label": "Repository",
                "value": issue.repository.full_name,
            })
        if issue.state:
            facts.append({"kind": "issue_state", "label": "GitHub state", "value": issue.state})
        if error_type:
            facts.append({"kind": "reported_error", "label": "Error reported", "value": error_type})
        if has_stack_trace:
            facts.append({"kind": "stack_trace", "label": "Stack trace", "value": "Stack frames are present in the issue body."})
        if has_repro:
            facts.append({"kind": "reproduction", "label": "Reproduction details", "value": "The issue contains a non-empty reproduction section; RepoMind has not run it."})
        facts.extend(self._reported_context_facts(issue.body or ""))
        for label in issue.labels or []:
            name = label.get("name") if isinstance(label, dict) else label
            if isinstance(name, str):
                facts.append({"kind": "github_label", "label": "GitHub label", "value": name})
        return facts

    def _root_cause_hypothesis(
        self, category: str, error_type: str | None, issue_text: str,
        evidence: list[dict[str, Any]],
        evidence_signals: dict[str, dict[str, Any]] | None = None,
    ) -> str:
        signals = evidence_signals or self.extract_evidence_signals("", issue_text)

        def excerpts(key: str) -> list[str]:
            return signals.get(key, {}).get("excerpts", [])

        def first(keys: tuple[str, ...]) -> str | None:
            return next((values[0] for key in keys if (values := excerpts(key))), None)

        def reported_summary(keys: tuple[str, ...]) -> str | None:
            values = [value for key in keys for value in excerpts(key)]
            return " | ".join(values[:4]) if values else None

        def first_report_sentence() -> str | None:
            prose = self._prose(issue_text)
            for line in prose.splitlines():
                line = re.sub(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+)", "", line).strip()
                if len(line) >= 18 and not line.startswith((">", "http")):
                    return line[:400]
            return None

        reported = first(("symptoms", "observed_results", "expected_behavior"))
        parts: list[str] = []
        if category in {"bug", "improvement"}:
            if reported:
                parts.append(f"Author-reported evidence: {reported}")
            actual = first(("observed_results", "symptoms"))
            expected = first(("expected_behavior",))
            if actual and expected:
                parts.append(f"The reported actual-versus-expected difference is: actual: {actual}; expected: {expected}")
            elif error_type:
                parts.append(f"The issue reports `{error_type}`; this identifies the observed failure signal, not its underlying cause.")
            if category == "improvement":
                parts.append("No root cause is established by an improvement request alone; validate the reported metric or behavior before selecting a change.")
            elif category == "bug":
                parts.append("Hypothesis (unverified): the failure lies somewhere on the path that produces the reported result. The issue text does not establish the mechanism or affected code path.")
                if re.search(r"\b(?:regression|regressed|worked before|worked in [\w.+-]+|started after (?:an? )?(?:upgrade|update|change))\b", self._assessment_prose(issue_text), re.I):
                    parts.append("The report suggests a regression, but does not by itself identify which change introduced it.")
        elif category == "documentation":
            requested_change = reported_summary(("observed_results", "expected_behavior", "symptoms", "environment", "configuration")) or first_report_sentence()
            if requested_change:
                parts.append(f"Author-reported documentation context: {requested_change}")
            parts.append("This is a request to clarify or change documentation; the report does not establish a runtime root cause or identify a verified documentation file.")
        elif category == "feature_request":
            request = reported_summary(("expected_behavior", "symptoms", "observed_results", "environment", "configuration")) or first_report_sentence()
            if request:
                parts.append(f"Author-reported requested behavior: {request}")
            parts.append("A feature request does not imply a defect. The report describes desired behavior; implementation constraints and acceptance criteria remain to be confirmed.")
        elif category == "question":
            parts.append("The issue asks for information. It does not by itself establish a defect or root cause.")
            if reported:
                parts.append(f"Relevant reported context: {reported}")
        else:
            if reported:
                parts.append(f"Author-reported context: {reported}")
            parts.append("The available evidence is insufficient to determine whether this is a defect, request, or question, or to support a root-cause hypothesis.")

        if evidence:
            refs = ", ".join(
                f"`{item['file_path']}` (L{item['start_line']}-L{item['end_line']})"
                for item in evidence[:3]
            )
            terms = sorted({term for item in evidence for term in item.get("matched_terms", [])})
            match_note = f"matching issue terms ({', '.join(terms)})" if terms else "issue-mentioned source paths"
            parts.append(f"Repository-index evidence (investigation lead, not a verified cause): {match_note} occur in {refs}. The snippets must be checked against the reported execution path.")
        else:
            parts.append("Repository-verified findings: none available. The issue report has not been independently reproduced, and no indexed source evidence supports a file-level or causal claim.")
        return " ".join(parts)

    def _recommendations(
        self, category: str, error_type: str | None, has_repro: bool,
        evidence: list[dict[str, Any]], issue_text: str, index_status: str,
        priority: str, priority_basis: str,
        evidence_signals: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, str]]:
        signals = evidence_signals or self.extract_evidence_signals("", issue_text)

        def has_signal(*keys: str) -> bool:
            return any(signals.get(key, {}).get("status") == "reported" for key in keys)

        def missing_details() -> str:
            missing = []
            if not has_signal("environment"):
                missing.append("runtime and dependency versions")
            if not has_signal("reproduction_steps", "executable_reproductions", "code_examples"):
                missing.append("a minimal reproduction")
            if not has_signal("observed_results", "symptoms"):
                missing.append("the observed result")
            if not has_signal("expected_behavior"):
                missing.append("the expected result")
            return ", ".join(missing)

        def reported_behavior() -> str | None:
            values = [
                excerpt
                for key in ("observed_results", "symptoms", "expected_behavior")
                for excerpt in signals.get(key, {}).get("excerpts", [])
            ]
            return " | ".join(values[:3]) if values else None

        if category == "bug":
            recs = []
            regression = bool(re.search(
                r"\b(?:regression|regressed|worked before|worked in [\w.+-]+|started after (?:an? )?(?:upgrade|update|change))\b",
                self._assessment_prose(issue_text), re.I,
            ))
            if has_repro or has_signal("reproduction_steps", "executable_reproductions"):
                behavior = reported_behavior()
                recs.append({
                    "action_type": "debug_fix",
                    "action_title": "Verify the reported behavior with the supplied reproduction",
                    "rationale": (f"Reported behavior: {behavior} " if behavior else "") + "The issue includes reproduction evidence, but RepoMind has not executed it. Compare the result with the reported expectation in the stated environment before selecting a change.",
                    "severity": "info",
                })
            else:
                missing = missing_details()
                behavior = reported_behavior()
                recs.append({
                    "action_type": "request_info",
                    "action_title": "Construct a minimal reproduction from the reported failure" if has_signal("symptoms", "observed_results") else "Clarify the behavior needed to investigate",
                    "rationale": (f"Reported behavior: {behavior} " if behavior else "") + "The issue does not include runnable reproduction steps. " + (f"Still needed: {missing}." if missing else "Use the reported environment and actual-versus-expected behavior to turn the report into a minimal test."),
                    "severity": "warning",
                })
            if regression:
                recs.append({
                    "action_type": "debug_fix",
                    "action_title": "Compare the last known working and first failing revisions",
                    "rationale": "The report describes a regression. Use any versions or change window already provided to reproduce on both sides and narrow the introducing change; do not assume the newest change is responsible without that comparison.",
                    "severity": "info",
                })
            if priority in {"P0_CRITICAL", "P1_HIGH"}:
                recs.append({
                    "action_type": "triage_label",
                    "action_title": "Escalate using the reported impact",
                    "rationale": priority_basis,
                    "severity": "critical" if priority == "P0_CRITICAL" else "warning",
                })

            if error_type:
                recs.append({
                    "action_type": "debug_fix",
                    "action_title": f"Trace the reported {error_type} through the failing path",
                    "rationale": "Start from the issue's stack frames or error location and confirm the path against the issue's versions and matching repository evidence. Do not infer an exception-handling fix from the error name alone.",
                    "severity": "warning",
                })

            if evidence:
                recs.append({
                    "action_type": "debug_fix",
                    "action_title": "Inspect repository evidence cited in this report",
                    "rationale": "The listed file ranges come from indexed chunks in this repository and matched terms from the issue; confirm whether they are on the failing path.",
                    "severity": "info",
                })
            elif index_status in {"not_indexed", "indexing", "partially_indexed"}:
                state_action = "Wait for repository indexing to finish" if index_status == "indexing" else "Index repository source code"
                recs.append({
                    "action_type": "debug_fix",
                    "action_title": state_action,
                    "rationale": f"Repository code index state is `{index_status.replace('_', ' ')}`. Matching source evidence is needed before RepoMind can identify affected files or support a code change.",
                    "severity": "warning",
                })
            else:
                recs.append({
                    "action_type": "debug_fix",
                    "action_title": "Search for the reported failure path in repository source",
                    "rationale": "No indexed source chunk matched the issue evidence. Search for the reported behavior or error symbols, then verify the relevant execution path before naming a file or proposing a change.",
                    "severity": "warning",
                })
            return recs
        if category == "feature_request":
            missing = []
            if not has_signal("expected_behavior"):
                missing.append("observable acceptance criteria")
            if not has_signal("environment", "configuration"):
                missing.append("the supported environment or configuration scope")
            rationale = "Review the requested behavior and agree on compatibility before implementation."
            if missing:
                rationale += " The report does not specify " + " and ".join(missing) + "."
            return [{
                "action_type": "triage_label",
                "action_title": "Define acceptance criteria for the requested behavior",
                "rationale": rationale,
                "severity": "info",
            }]
        if category == "documentation":
            context_parts = [
                excerpt
                for key in ("observed_results", "expected_behavior", "symptoms")
                for excerpt in signals.get(key, {}).get("excerpts", [])
            ]
            context = " | ".join(context_parts[:3]) if context_parts else None
            source_state = "The repository source index is not indexed, so the affected page and exact edit cannot be verified." if index_status == "not_indexed" else "Confirm the matching documentation page from repository evidence before naming or editing it."
            rationale = "Use the reported request and observed behavior to make a narrowly scoped documentation change; preserve any uncertainty the reporter expressed. " + source_state
            if context:
                rationale = f"Issue-reported context: {context} " + rationale
            if evidence:
                rationale += " Matching indexed snippets are references to review, not proof that they are the correct documentation location."
            return [{
                "action_type": "triage_label",
                "action_title": "Update the relevant documentation based on the reported request",
                "rationale": rationale,
                "severity": "info",
            }]
        if category == "question":
            return [{
                "action_type": "debug_fix" if evidence else "request_info",
                "action_title": "Answer from the matching repository evidence" if evidence else "Find a repository-backed answer to the question",
                "rationale": ("Use only the matching indexed references and issue-provided context; the references are not proof on their own." if evidence else "No matching indexed source evidence is available. Check the repository documentation or source for the answer, and ask the reporter only for context that is necessary to resolve an ambiguity in the question."),
                "severity": "info",
            }]
        if category == "improvement":
            observed = has_signal("observed_results", "symptoms")
            return [{
                "action_type": "debug_fix",
                "action_title": "Validate the reported metric before choosing an optimization",
                "rationale": "Compare a reproducible baseline with the desired outcome under the reported workload and configuration. " + ("The report includes an observed result." if observed else "The issue does not include a measured result; establish a baseline before selecting a change."),
                "severity": "info",
            }]
        missing = []
        if not has_signal("observed_results", "symptoms"):
            missing.append("what happened")
        if not has_signal("expected_behavior"):
            missing.append("what should have happened")
        if not has_signal("reproduction_steps", "executable_reproductions"):
            missing.append("steps to reproduce")
        return [{
            "action_type": "request_info",
            "action_title": "Clarify the missing issue context",
            "rationale": ("Available issue text does not support a reliable category or implementation recommendation yet. Still needed: " + ", ".join(missing) + ".") if missing else "The issue contains behavior details, but its intended category remains ambiguous. Confirm whether the report describes a defect, a requested capability, or a question before choosing an implementation action.",
            "severity": "warning",
        }]

    def diagnose_issue(self, issue: Issue, db: Session) -> IssueAnalysis:
        full_text = f"{issue.title}\n\n{issue.body or ''}"
        has_stack_trace, extracted_tb = self.extract_stack_trace(full_text)
        error_type = self.extract_error_type(full_text)
        has_repro = self.has_reproduction_steps(issue.body or "")
        evidence_signals = self.extract_evidence_signals(issue.title, issue.body or "")
        category, category_score = self.classify_category(
            issue.title, issue.body or "", issue.labels, bool(error_type or has_stack_trace), evidence_signals
        )
        priority, priority_score = self.estimate_priority(
            category, full_text, bool(error_type), has_stack_trace, issue.labels, evidence_signals
        )
        index_status = db.query(CodeIndexStatus).filter(
            CodeIndexStatus.repository_id == issue.repository_id
        ).first()
        repository_index_status = index_status.status if index_status else "not_indexed"
        repository_indexed_at = index_status.last_indexed_at if index_status else None
        evidence = self._repository_evidence(issue, db, full_text, error_type, extracted_tb)
        affected_files = list(dict.fromkeys(item["file_path"] for item in evidence))
        issue_facts = self._issue_facts(issue, error_type, has_stack_trace, has_repro)
        assumptions = ["RepoMind has not run the issue's reproduction or independently verified its reported behavior."]
        if not evidence:
            if repository_index_status == "not_indexed":
                assumptions.append("Repository code has not been indexed; affected files and code changes cannot be verified yet.")
            elif repository_index_status == "indexing":
                assumptions.append("Repository code indexing is still in progress; affected files and code changes may become verifiable when it finishes.")
            elif repository_index_status == "partially_indexed":
                assumptions.append("Repository code indexing is incomplete; no matching source chunk was found in the indexed portion.")
            elif repository_index_status == "failed":
                assumptions.append("Repository code indexing failed; affected files and code changes cannot be verified from source evidence.")
            else:
                assumptions.append("The repository is indexed, but no source chunk matched the reported error symbols; affected files and code changes remain unverified.")
        elif repository_index_status == "partially_indexed":
            assumptions.append("Repository indexing is incomplete, so the matching source evidence may not cover all affected code.")
        root_cause = self._root_cause_hypothesis(category, error_type, full_text, evidence, evidence_signals)
        priority_basis = self.priority_rationale(priority, issue.labels or [], full_text, category)
        recommendations = self._recommendations(
            category, error_type, has_repro, evidence, full_text,
            repository_index_status, priority, priority_basis, evidence_signals,
        )

        analysis = db.query(IssueAnalysis).filter(IssueAnalysis.issue_id == issue.id).first()
        now = datetime.now(timezone.utc)
        values = {
            "category": category,
            "priority": priority,
            "confidence": round((category_score + priority_score) / 2, 2),
            "model_version": self.model_version,
            "root_cause_hypothesis": root_cause,
            "error_type": error_type,
            "stack_trace_detected": has_stack_trace,
            "reproduction_steps_detected": has_repro,
            "extracted_stack_trace": extracted_tb,
            "affected_components": affected_files,
            "issue_facts": issue_facts,
            "repository_evidence": evidence,
            "assumptions": assumptions,
            "priority_rationale": priority_basis,
            "repository_index_status": repository_index_status,
            "repository_indexed_at": repository_indexed_at,
            "source_content_digest": self.issue_content_digest(issue.title, issue.body),
            "fix_target_file": None,
            "proposed_code_patch": None,
            "verification_test_code": None,
            "patch_explanation": (
                "No patch was generated. A safe change requires confirming the failing code path against repository source and the issue's environment; the report does not contain a verified patch context."
            ),
            "analyzed_at": now,
        }
        if analysis:
            for key, value in values.items():
                setattr(analysis, key, value)
        else:
            analysis = IssueAnalysis(issue_id=issue.id, **values)
            db.add(analysis)
        db.flush()

        db.query(ActionRecommendation).filter(ActionRecommendation.issue_id == issue.id).delete()
        for item in recommendations:
            db.add(ActionRecommendation(
                issue_id=issue.id,
                action_type=item["action_type"],
                action_title=item["action_title"],
                rationale=item["rationale"],
                severity=item["severity"],
                created_at=now,
            ))
        db.commit()
        db.refresh(analysis)
        return analysis
