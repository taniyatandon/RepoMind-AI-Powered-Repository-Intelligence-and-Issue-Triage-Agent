import React, { useEffect, useState } from "react";
import { apiDiagnoseIssue, apiGetIssueAnalysis } from "../api";
import { Issue, IssueAnalysis } from "../types";
import {
  AlertCircle,
  Calendar,
  Check,
  CheckCircle2,
  Code2,
  Copy,
  Cpu,
  ExternalLink,
  FileCode,
  Lightbulb,
  Loader2,
  MessageSquare,
  RefreshCw,
  Sparkles,
  Tag,
  Terminal,
  User,
  Wrench,
  X,
} from "lucide-react";

interface IssueDetailModalProps {
  issue: Issue | null;
  onClose: () => void;
}

export const IssueDetailModal: React.FC<IssueDetailModalProps> = ({
  issue,
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<"details" | "diagnosis" | "solution">("details");
  const [analysis, setAnalysis] = useState<IssueAnalysis | null>(null);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [copiedPatch, setCopiedPatch] = useState(false);
  const [copiedTest, setCopiedTest] = useState(false);

  useEffect(() => {
    if (!issue) {
      setAnalysis(null);
      setActiveTab("details");
      setAnalysisError(null);
      return;
    }

    // Auto-fetch existing analysis when issue opens
    let isCancelled = false;
    setLoadingAnalysis(true);
    setAnalysisError(null);

    apiGetIssueAnalysis(issue.id)
      .then((data) => {
        if (!isCancelled) setAnalysis(data);
      })
      .catch((err) => {
        if (!isCancelled) setAnalysisError(err.message);
      })
      .finally(() => {
        if (!isCancelled) setLoadingAnalysis(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [issue]);

  if (!issue) return null;

  const handleRunDiagnosis = async () => {
    setLoadingAnalysis(true);
    setAnalysisError(null);
    try {
      const result = await apiDiagnoseIssue(issue.id);
      setAnalysis(result);
    } catch (err: any) {
      setAnalysisError(err.message || "Failed to run diagnosis.");
    } finally {
      setLoadingAnalysis(false);
    }
  };

  const handleCopy = (text: string, type: "patch" | "test") => {
    navigator.clipboard.writeText(text);
    if (type === "patch") {
      setCopiedPatch(true);
      setTimeout(() => setCopiedPatch(false), 2000);
    } else {
      setCopiedTest(true);
      setTimeout(() => setCopiedTest(false), 2000);
    }
  };

  const getPriorityStyle = (priority?: string) => {
    switch (priority) {
      case "P0_CRITICAL":
        return { backgroundColor: "rgba(239, 68, 68, 0.15)", color: "#f87171", borderColor: "rgba(239, 68, 68, 0.4)" };
      case "P1_HIGH":
        return { backgroundColor: "rgba(245, 158, 11, 0.15)", color: "#fbbf24", borderColor: "rgba(245, 158, 11, 0.4)" };
      case "P2_MEDIUM":
        return { backgroundColor: "rgba(99, 102, 241, 0.15)", color: "#a5b4fc", borderColor: "rgba(99, 102, 241, 0.4)" };
      default:
        return { backgroundColor: "rgba(107, 114, 128, 0.15)", color: "#9ca3af", borderColor: "rgba(107, 114, 128, 0.4)" };
    }
  };

  const renderDiffLine = (line: string, idx: number) => {
    let color = "#cbd5e1";
    let bg = "transparent";

    if (line.startsWith("+") && !line.startsWith("+++")) {
      color = "#6ee7b7";
      bg = "rgba(16, 185, 129, 0.14)";
    } else if (line.startsWith("-") && !line.startsWith("---")) {
      color = "#fca5a5";
      bg = "rgba(239, 68, 68, 0.14)";
    } else if (line.startsWith("@@")) {
      color = "#93c5fd";
      bg = "rgba(59, 130, 246, 0.12)";
    } else if (line.startsWith("---") || line.startsWith("+++")) {
      color = "#c084fc";
      bg = "rgba(168, 85, 247, 0.12)";
    }

    return (
      <div
        key={idx}
        style={{
          padding: "2px 10px",
          backgroundColor: bg,
          color: color,
          fontFamily: "var(--font-mono)",
          fontSize: "0.8125rem",
          whiteSpace: "pre-wrap",
          wordBreak: "break-all",
          lineHeight: 1.5,
        }}
      >
        {line}
      </div>
    );
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: "880px",
          width: "95%",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          padding: "1.75rem",
        }}
      >
        {/* Modal Header */}
        <div className="modal-header" style={{ alignItems: "flex-start", gap: "1rem", flexShrink: 0 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.45rem", flexWrap: "wrap" }}>
              <span
                className={`badge ${
                  issue.state.toLowerCase() === "open" ? "badge-open" : "badge-closed"
                }`}
              >
                {issue.state.toUpperCase()}
              </span>

              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  color: "var(--text-muted)",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                }}
              >
                #{issue.issue_number}
              </span>

              {/* Triage Badges if analyzed */}
              {analysis && (
                <>
                  <span
                    className="badge"
                    style={{
                      backgroundColor: "rgba(99, 102, 241, 0.14)",
                      color: "#a5b4fc",
                      border: "1px solid rgba(99, 102, 241, 0.35)",
                      textTransform: "capitalize",
                    }}
                  >
                    <Sparkles size={11} color="#818cf8" />
                    {analysis.category.replace("_", " ")} ({Math.round(analysis.confidence * 100)}%)
                  </span>
                  <span
                    className="badge"
                    style={getPriorityStyle(analysis.priority)}
                  >
                    {analysis.priority}
                  </span>
                </>
              )}
            </div>

            <h2 className="modal-title" style={{ fontSize: "1.25rem", lineHeight: 1.4, wordBreak: "break-word" }}>
              {issue.title}
            </h2>
          </div>

          <button className="close-btn" onClick={onClose} aria-label="Close dialog">
            <X size={18} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            borderBottom: "1px solid var(--border-subtle)",
            paddingBottom: "0.5rem",
            marginBottom: "1.25rem",
            flexShrink: 0,
            flexWrap: "wrap",
          }}
        >
          {/* Tab 1: Details */}
          <button
            onClick={() => setActiveTab("details")}
            style={{
              padding: "0.45rem 0.9rem",
              background: activeTab === "details" ? "var(--bg-elevated)" : "transparent",
              color: activeTab === "details" ? "var(--text-primary)" : "var(--text-secondary)",
              border: activeTab === "details" ? "1px solid var(--border-color)" : "1px solid transparent",
              borderRadius: "var(--radius-sm)",
              cursor: "pointer",
              fontWeight: 500,
              fontSize: "0.825rem",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              transition: "all var(--transition-fast)",
            }}
          >
            <span>Issue Details</span>
          </button>

          {/* Tab 2: Diagnosis */}
          <button
            onClick={() => setActiveTab("diagnosis")}
            style={{
              padding: "0.45rem 0.9rem",
              background:
                activeTab === "diagnosis"
                  ? "linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(139, 92, 246, 0.2))"
                  : "transparent",
              color: activeTab === "diagnosis" ? "#ffffff" : "var(--text-secondary)",
              border:
                activeTab === "diagnosis"
                  ? "1px solid rgba(99, 102, 241, 0.5)"
                  : "1px solid transparent",
              borderRadius: "var(--radius-sm)",
              cursor: "pointer",
              fontWeight: 600,
              fontSize: "0.825rem",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              transition: "all var(--transition-fast)",
            }}
          >
            <Cpu size={14} color="#818cf8" />
            <span>AI Diagnostic Inspector</span>
            {analysis && (
              <span
                style={{
                  fontSize: "0.675rem",
                  padding: "1px 6px",
                  borderRadius: "var(--radius-full)",
                  backgroundColor: "#6366f1",
                  color: "#ffffff",
                  fontWeight: 700,
                }}
              >
                Ready
              </span>
            )}
          </button>

          {/* Tab 3: Proposed Code Solution */}
          <button
            onClick={() => setActiveTab("solution")}
            style={{
              padding: "0.45rem 0.9rem",
              background:
                activeTab === "solution"
                  ? "linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(99, 102, 241, 0.2))"
                  : "transparent",
              color: activeTab === "solution" ? "#ffffff" : "var(--text-secondary)",
              border:
                activeTab === "solution"
                  ? "1px solid rgba(16, 185, 129, 0.5)"
                  : "1px solid transparent",
              borderRadius: "var(--radius-sm)",
              cursor: "pointer",
              fontWeight: 600,
              fontSize: "0.825rem",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              transition: "all var(--transition-fast)",
            }}
          >
            <Wrench size={14} color="#34d399" />
            <span>Proposed Code Solution</span>
            {analysis?.proposed_code_patch && (
              <span
                style={{
                  fontSize: "0.675rem",
                  padding: "1px 6px",
                  borderRadius: "var(--radius-full)",
                  backgroundColor: "#10b981",
                  color: "#ffffff",
                  fontWeight: 700,
                }}
              >
                Patch
              </span>
            )}
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div style={{ flex: 1, overflowY: "auto", paddingRight: "0.25rem" }}>
          {activeTab === "details" ? (
            <>
              {/* Metadata Bar */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "1.25rem",
                  flexWrap: "wrap",
                  padding: "0.75rem 1rem",
                  backgroundColor: "rgba(255, 255, 255, 0.03)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                  marginBottom: "1.25rem",
                  fontSize: "0.8125rem",
                  color: "var(--text-secondary)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <User size={14} color="#818cf8" />
                  <span>
                    Author: <strong style={{ color: "var(--text-primary)" }}>{issue.author || "Unknown"}</strong>
                  </span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <Calendar size={14} color="var(--text-muted)" />
                  <span>{new Date(issue.created_at).toLocaleString()}</span>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <MessageSquare size={14} color="var(--text-muted)" />
                  <span>{issue.comments_count} Comments</span>
                </div>

                <a
                  href={issue.html_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    marginLeft: "auto",
                    display: "flex",
                    alignItems: "center",
                    gap: "0.35rem",
                    color: "var(--accent-primary)",
                    textDecoration: "none",
                    fontWeight: 500,
                  }}
                >
                  <span>View on GitHub</span>
                  <ExternalLink size={13} />
                </a>
              </div>

              {/* Labels Section */}
              {issue.labels && issue.labels.length > 0 && (
                <div style={{ marginBottom: "1.25rem" }}>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.35rem",
                      marginBottom: "0.5rem",
                      fontSize: "0.75rem",
                      fontWeight: 600,
                      color: "var(--text-muted)",
                      letterSpacing: "0.04em",
                      textTransform: "uppercase",
                    }}
                  >
                    <Tag size={12} />
                    <span>Labels</span>
                  </div>
                  <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                    {issue.labels.map((lbl, idx) => {
                      const name = typeof lbl === "string" ? lbl : lbl.name;
                      const color = typeof lbl === "string" ? "4b5563" : lbl.color || "4b5563";
                      return (
                        <span
                          key={idx}
                          className="badge badge-label"
                          style={{
                            backgroundColor: `#${color}18`,
                            color: `#${color}`,
                            borderColor: `#${color}40`,
                          }}
                        >
                          {name}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Issue Description Body */}
              <div>
                <div
                  style={{
                    fontSize: "0.75rem",
                    color: "var(--text-muted)",
                    marginBottom: "0.5rem",
                    fontWeight: 600,
                    letterSpacing: "0.04em",
                    textTransform: "uppercase",
                  }}
                >
                  Description
                </div>

                <div
                  style={{
                    backgroundColor: "rgba(255, 255, 255, 0.02)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-sm)",
                    padding: "1rem",
                    fontSize: "0.875rem",
                    color: "var(--text-primary)",
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                    lineHeight: 1.6,
                    maxHeight: "360px",
                    overflowY: "auto",
                  }}
                >
                  {issue.body || "No description provided."}
                </div>
              </div>
            </>
          ) : activeTab === "diagnosis" ? (
            <div>
              {/* Diagnosis Header Controls */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "1.25rem",
                  flexWrap: "wrap",
                  gap: "0.75rem",
                }}
              >
                <div>
                  <h3 style={{ fontSize: "1.05rem", fontWeight: 700 }}>AI Root Cause & Error Inspector</h3>
                  <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    Deep neural analysis of stack traces, affected subsystems, and reproduction steps
                  </p>
                </div>

                <button
                  className="btn btn-primary btn-sm"
                  onClick={handleRunDiagnosis}
                  disabled={loadingAnalysis}
                >
                  {loadingAnalysis ? (
                    <>
                      <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />
                      <span>Diagnosing...</span>
                    </>
                  ) : (
                    <>
                      <RefreshCw size={13} />
                      <span>{analysis ? "Re-run Diagnosis" : "Run AI Diagnosis"}</span>
                    </>
                  )}
                </button>
              </div>

              {analysisError && (
                <div className="alert alert-danger">
                  <AlertCircle size={16} style={{ flexShrink: 0, marginTop: "2px" }} />
                  <div>{analysisError}</div>
                </div>
              )}

              {loadingAnalysis && !analysis && (
                <div style={{ textAlign: "center", padding: "3rem 1rem" }}>
                  <div className="spinner" style={{ margin: "0 auto 1rem auto" }} />
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                    Analyzing issue context, stack traces, and reproduction signals...
                  </p>
                </div>
              )}

              {!loadingAnalysis && !analysis && (
                <div className="empty-state" style={{ padding: "3rem 1.5rem" }}>
                  <Cpu size={36} className="empty-state-icon" />
                  <h4 className="empty-state-title">No AI Diagnosis Run Yet</h4>
                  <p className="empty-state-desc">
                    Click "Run AI Diagnosis" to inspect this issue for root causes, detect stack traces, and extract reproduction criteria.
                  </p>
                  <button className="btn btn-primary btn-sm" onClick={handleRunDiagnosis}>
                    <Sparkles size={14} />
                    <span>Diagnose Issue Now</span>
                  </button>
                </div>
              )}

              {analysis && (
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  {/* Overview Cards Grid */}
                  <div
                    style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                      gap: "0.75rem",
                    }}
                  >
                    <div className="card" style={{ padding: "0.85rem 1rem" }}>
                      <span style={{ fontSize: "0.725rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                        Classification
                      </span>
                      <div style={{ fontSize: "0.95rem", fontWeight: 700, marginTop: "0.25rem", textTransform: "capitalize" }}>
                        {analysis.category.replace("_", " ")}
                      </div>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                        Confidence: {Math.round(analysis.confidence * 100)}%
                      </span>
                    </div>

                    <div className="card" style={{ padding: "0.85rem 1rem" }}>
                      <span style={{ fontSize: "0.725rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                        Priority Triage
                      </span>
                      <div style={{ fontSize: "0.95rem", fontWeight: 700, marginTop: "0.25rem" }}>
                        <span className="badge" style={getPriorityStyle(analysis.priority)}>
                          {analysis.priority}
                        </span>
                      </div>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                        Model: {analysis.model_version}
                      </span>
                    </div>

                    <div className="card" style={{ padding: "0.85rem 1rem" }}>
                      <span style={{ fontSize: "0.725rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
                        Signals Detected
                      </span>
                      <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.35rem", flexWrap: "wrap" }}>
                        <span
                          className={`badge ${
                            analysis.stack_trace_detected ? "badge-open" : "badge-label"
                          }`}
                          style={{ fontSize: "0.7rem" }}
                        >
                          Stack Trace: {analysis.stack_trace_detected ? "Yes" : "No"}
                        </span>
                        <span
                          className={`badge ${
                            analysis.reproduction_steps_detected ? "badge-open" : "badge-label"
                          }`}
                          style={{ fontSize: "0.7rem" }}
                        >
                          Repro Steps: {analysis.reproduction_steps_detected ? "Yes" : "No"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Root Cause Hypothesis Card */}
                  {analysis.root_cause_hypothesis && (
                    <div
                      className="card"
                      style={{
                        padding: "1rem 1.25rem",
                        backgroundColor: "rgba(99, 102, 241, 0.08)",
                        border: "1px solid rgba(99, 102, 241, 0.25)",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem" }}>
                        <Lightbulb size={16} color="#818cf8" />
                        <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#a5b4fc" }}>
                          Root Cause Hypothesis
                        </span>
                      </div>
                      <p style={{ fontSize: "0.85rem", color: "var(--text-primary)", lineHeight: 1.5 }}>
                        {analysis.root_cause_hypothesis}
                      </p>
                    </div>
                  )}

                  {/* Affected Subsystems */}
                  {analysis.affected_components && analysis.affected_components.length > 0 && (
                    <div>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", display: "block", marginBottom: "0.4rem" }}>
                        Affected Components & Modules
                      </span>
                      <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                        {analysis.affected_components.map((c, i) => (
                          <span
                            key={i}
                            className="badge badge-label"
                            style={{
                              fontFamily: "var(--font-mono)",
                              fontSize: "0.75rem",
                              backgroundColor: "rgba(255, 255, 255, 0.04)",
                            }}
                          >
                            {c}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Extracted Stack Trace */}
                  {analysis.extracted_stack_trace && (
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.4rem" }}>
                        <Terminal size={14} color="#f59e0b" />
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 600 }}>
                          Extracted Stack Trace
                        </span>
                      </div>
                      <div className="code-container" style={{ padding: "0.75rem 1rem", maxHeight: "200px" }}>
                        <pre style={{ margin: 0, color: "#fca5a5" }}>{analysis.extracted_stack_trace}</pre>
                      </div>
                    </div>
                  )}

                  {/* Actionable Recommendations */}
                  {analysis.recommendations && analysis.recommendations.length > 0 && (
                    <div>
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", display: "block", marginBottom: "0.5rem", fontWeight: 600 }}>
                        Actionable Recommendations
                      </span>
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                        {analysis.recommendations.map((rec, i) => (
                          <div
                            key={i}
                            className="card"
                            style={{
                              padding: "0.75rem 1rem",
                              display: "flex",
                              alignItems: "flex-start",
                              gap: "0.75rem",
                            }}
                          >
                            <div
                              style={{
                                width: "6px",
                                height: "6px",
                                borderRadius: "50%",
                                backgroundColor:
                                  rec.severity === "critical"
                                    ? "#ef4444"
                                    : rec.severity === "warning"
                                    ? "#f59e0b"
                                    : "#38bdf8",
                                marginTop: "6px",
                                flexShrink: 0,
                              }}
                            />
                            <div>
                              <strong style={{ fontSize: "0.85rem", color: "var(--text-primary)" }}>
                                {rec.action_title}
                              </strong>
                              <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: "0.2rem" }}>
                                {rec.rationale}
                              </p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            /* Solution Tab */
            <div>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: "1.25rem",
                  flexWrap: "wrap",
                  gap: "0.75rem",
                }}
              >
                <div>
                  <h3 style={{ fontSize: "1.05rem", fontWeight: 700 }}>Proposed Automated Code Fix</h3>
                  <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    AI-generated diff patch and regression test for verification
                  </p>
                </div>

                {!analysis && (
                  <button className="btn btn-primary btn-sm" onClick={handleRunDiagnosis} disabled={loadingAnalysis}>
                    <Sparkles size={14} />
                    <span>Run Diagnosis to Generate Fix</span>
                  </button>
                )}
              </div>

              {!analysis?.proposed_code_patch ? (
                <div className="empty-state" style={{ padding: "3rem 1.5rem" }}>
                  <Wrench size={36} className="empty-state-icon" />
                  <h4 className="empty-state-title">No Code Patch Generated</h4>
                  <p className="empty-state-desc">
                    Diagnose this issue to generate an automated code fix patch and corresponding regression test.
                  </p>
                  <button className="btn btn-primary btn-sm" onClick={handleRunDiagnosis} disabled={loadingAnalysis}>
                    <Sparkles size={14} />
                    <span>Generate Fix Patch</span>
                  </button>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                  {/* Target File */}
                  {analysis.fix_target_file && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "0.5rem",
                        padding: "0.6rem 0.85rem",
                        backgroundColor: "rgba(255, 255, 255, 0.03)",
                        border: "1px solid var(--border-subtle)",
                        borderRadius: "var(--radius-sm)",
                        fontSize: "0.825rem",
                      }}
                    >
                      <FileCode size={15} color="#818cf8" />
                      <span style={{ color: "var(--text-muted)" }}>Target File:</span>
                      <code style={{ color: "#ffffff", fontWeight: 600 }}>{analysis.fix_target_file}</code>
                    </div>
                  )}

                  {/* Patch Explanation */}
                  {analysis.patch_explanation && (
                    <div
                      className="card"
                      style={{
                        padding: "0.85rem 1rem",
                        backgroundColor: "rgba(16, 185, 129, 0.07)",
                        border: "1px solid rgba(16, 185, 129, 0.25)",
                      }}
                    >
                      <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "#34d399", display: "block", marginBottom: "0.25rem" }}>
                        Patch Rationale & Design
                      </span>
                      <p style={{ fontSize: "0.825rem", color: "var(--text-primary)", lineHeight: 1.5 }}>
                        {analysis.patch_explanation}
                      </p>
                    </div>
                  )}

                  {/* Unified Diff Patch Viewer */}
                  <div>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "0.4rem",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <Code2 size={14} color="#818cf8" />
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 600 }}>
                          Unified Code Diff Patch
                        </span>
                      </div>

                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleCopy(analysis.proposed_code_patch!, "patch")}
                        style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
                      >
                        {copiedPatch ? <Check size={12} color="#34d399" /> : <Copy size={12} />}
                        <span>{copiedPatch ? "Copied Patch!" : "Copy Patch"}</span>
                      </button>
                    </div>

                    <div className="code-container" style={{ maxHeight: "300px" }}>
                      {analysis.proposed_code_patch.split("\n").map((line, idx) =>
                        renderDiffLine(line, idx)
                      )}
                    </div>
                  </div>

                  {/* Regression Test Code Block */}
                  {analysis.verification_test_code && (
                    <div>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          marginBottom: "0.4rem",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                          <CheckCircle2 size={14} color="#34d399" />
                          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.04em", fontWeight: 600 }}>
                            Automated Verification & Regression Test
                          </span>
                        </div>

                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleCopy(analysis.verification_test_code!, "test")}
                          style={{ padding: "0.25rem 0.5rem", fontSize: "0.75rem" }}
                        >
                          {copiedTest ? <Check size={12} color="#34d399" /> : <Copy size={12} />}
                          <span>{copiedTest ? "Copied Test!" : "Copy Test"}</span>
                        </button>
                      </div>

                      <div className="code-container" style={{ padding: "0.75rem 1rem", maxHeight: "250px" }}>
                        <pre style={{ margin: 0, color: "#93c5fd" }}>
                          {analysis.verification_test_code}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
