import React, { useEffect, useState } from "react";
import { apiGetIssueByNumber, apiGetPullRequestChanges, apiSyncPullRequestDiffs } from "../api";
import { CodeDiff, Issue, PullRequest, PullRequestChanges, ResolvedIssueSummary } from "../types";
import {
  AlertCircle,
  Calendar,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Columns,
  Copy,
  ExternalLink,
  FileCode,
  GitCommit,
  GitMerge,
  GitPullRequest,
  List,
  Loader2,
  RefreshCw,
  Tag,
  User,
  Wrench,
  X,
} from "lucide-react";

interface PullRequestDetailModalProps {
  pr: PullRequest | null;
  onClose: () => void;
  onSelectIssue?: (issue: Issue) => void;
}

interface SplitDiffRow {
  type: "hunk-header" | "row";
  hunkHeader?: string;
  left?: {
    lineNo: number | null;
    content: string;
    type: "normal" | "deletion" | "empty";
  };
  right?: {
    lineNo: number | null;
    content: string;
    type: "normal" | "addition" | "empty";
  };
}

function parseUnifiedDiffToSplit(diffContent: string): SplitDiffRow[] {
  const rows: SplitDiffRow[] = [];
  const lines = diffContent.split("\n");

  let oldLine = 1;
  let newLine = 1;

  let pendingDeletions: { lineNo: number; content: string }[] = [];
  let pendingAdditions: { lineNo: number; content: string }[] = [];

  const flushPending = () => {
    const maxLen = Math.max(pendingDeletions.length, pendingAdditions.length);
    for (let i = 0; i < maxLen; i++) {
      const del = pendingDeletions[i];
      const add = pendingAdditions[i];

      rows.push({
        type: "row",
        left: del
          ? { lineNo: del.lineNo, content: del.content, type: "deletion" }
          : { lineNo: null, content: "", type: "empty" },
        right: add
          ? { lineNo: add.lineNo, content: add.content, type: "addition" }
          : { lineNo: null, content: "", type: "empty" },
      });
    }
    pendingDeletions = [];
    pendingAdditions = [];
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("@@")) {
      flushPending();
      const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)/);
      if (match) {
        oldLine = parseInt(match[1], 10);
        newLine = parseInt(match[2], 10);
      }
      rows.push({
        type: "hunk-header",
        hunkHeader: line,
      });
    } else if (line.startsWith("-") && !line.startsWith("---")) {
      pendingDeletions.push({
        lineNo: oldLine++,
        content: line.slice(1),
      });
    } else if (line.startsWith("+") && !line.startsWith("+++")) {
      pendingAdditions.push({
        lineNo: newLine++,
        content: line.slice(1),
      });
    } else if (line.startsWith(" ")) {
      flushPending();
      rows.push({
        type: "row",
        left: {
          lineNo: oldLine++,
          content: line.slice(1),
          type: "normal",
        },
        right: {
          lineNo: newLine++,
          content: line.slice(1),
          type: "normal",
        },
      });
    } else if (line.startsWith("---") || line.startsWith("+++")) {
      continue;
    } else if (line.length > 0) {
      flushPending();
      rows.push({
        type: "row",
        left: {
          lineNo: oldLine++,
          content: line,
          type: "normal",
        },
        right: {
          lineNo: newLine++,
          content: line,
          type: "normal",
        },
      });
    }
  }

  flushPending();
  return rows;
}

export const PullRequestDetailModal: React.FC<PullRequestDetailModalProps> = ({
  pr,
  onClose,
  onSelectIssue,
}) => {
  const [activeTab, setActiveTab] = useState<"diffs" | "overview" | "commits">("diffs");
  const [diffMode, setDiffMode] = useState<"split" | "unified">("split");
  const [changes, setChanges] = useState<PullRequestChanges | null>(null);
  const [loadingChanges, setLoadingChanges] = useState(false);
  const [syncingChanges, setSyncingChanges] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [expandedFiles, setExpandedFiles] = useState<Record<number, boolean>>({});
  const [openingIssueNum, setOpeningIssueNum] = useState<number | null>(null);

  useEffect(() => {
    if (!pr) {
      setChanges(null);
      setActiveTab("diffs");
      setError(null);
      setExpandedFiles({});
      return;
    }

    let isCancelled = false;
    setLoadingChanges(true);
    setError(null);

    apiGetPullRequestChanges(pr.id, true)
      .then((data) => {
        if (!isCancelled) {
          setChanges(data);
          const initialExpanded: Record<number, boolean> = {};
          data.files.slice(0, 5).forEach((f) => {
            initialExpanded[f.id] = true;
          });
          setExpandedFiles(initialExpanded);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          setError(err.message || "Failed to load commits and diffs.");
        }
      })
      .finally(() => {
        if (!isCancelled) setLoadingChanges(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [pr]);

  if (!pr) return null;

  const isMerged = pr.is_merged || pr.state.toLowerCase() === "merged";
  const isOpen = pr.state.toLowerCase() === "open";

  const handleCopyLink = () => {
    if (pr.html_url) {
      navigator.clipboard.writeText(pr.html_url);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2000);
    }
  };

  const handleForceSyncDiffs = async () => {
    setSyncingChanges(true);
    setError(null);
    try {
      const data = await apiSyncPullRequestDiffs(pr.id);
      setChanges(data);
      const initialExpanded: Record<number, boolean> = {};
      data.files.slice(0, 5).forEach((f) => {
        initialExpanded[f.id] = true;
      });
      setExpandedFiles(initialExpanded);
    } catch (err: any) {
      setError(err.message || "Failed to sync diffs from GitHub.");
    } finally {
      setSyncingChanges(false);
    }
  };

  const handleInspectIssue = async (resIssue: ResolvedIssueSummary) => {
    if (!onSelectIssue) return;
    setOpeningIssueNum(resIssue.issue_number);
    try {
      const fullIssue = await apiGetIssueByNumber(pr.repository_id, resIssue.issue_number);
      onClose();
      onSelectIssue(fullIssue);
    } catch (err: any) {
      // If issue not stored locally, navigate to external GitHub issue
      if (resIssue.html_url) {
        window.open(resIssue.html_url, "_blank");
      }
    } finally {
      setOpeningIssueNum(null);
    }
  };

  const toggleFileExpansion = (fileId: number) => {
    setExpandedFiles((prev) => ({
      ...prev,
      [fileId]: !prev[fileId],
    }));
  };

  const renderUnifiedLine = (line: string, idx: number) => {
    let bg = "transparent";
    let color = "var(--text-secondary)";

    if (line.startsWith("+") && !line.startsWith("+++")) {
      color = "#34d399";
      bg = "rgba(16, 185, 129, 0.15)";
    } else if (line.startsWith("-") && !line.startsWith("---")) {
      color = "#f87171";
      bg = "rgba(239, 68, 68, 0.15)";
    } else if (line.startsWith("@@")) {
      color = "#60a5fa";
      bg = "rgba(59, 130, 246, 0.12)";
    } else if (line.startsWith("---") || line.startsWith("+++")) {
      color = "#a78bfa";
      bg = "rgba(139, 92, 246, 0.1)";
    }

    return (
      <div
        key={idx}
        style={{
          padding: "2px 8px",
          backgroundColor: bg,
          color: color,
          fontFamily: "var(--font-mono)",
          fontSize: "0.82rem",
          whiteSpace: "pre-wrap",
          wordBreak: "break-all",
          lineHeight: 1.5,
        }}
      >
        {line}
      </div>
    );
  };

  const renderSplitDiffTable = (diffContent: string) => {
    const rows = parseUnifiedDiffToSplit(diffContent);

    return (
      <div style={{ overflowX: "auto" }}>
        {/* Split Table Column Headers */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            borderBottom: "1px solid var(--border-color)",
            backgroundColor: "rgba(17, 24, 39, 0.75)",
            fontSize: "0.78rem",
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          <div
            style={{
              padding: "6px 12px",
              color: "#f87171",
              borderRight: "1px solid var(--border-color)",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor: "#ef4444",
                display: "inline-block",
              }}
            />
            <span>Before Pushing (Original / Base)</span>
          </div>

          <div
            style={{
              padding: "6px 12px",
              color: "#34d399",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor: "#10b981",
                display: "inline-block",
              }}
            />
            <span>After Pushing (Modified / PR Changes)</span>
          </div>
        </div>

        {/* Rows */}
        <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.81rem", lineHeight: 1.5 }}>
          {rows.map((row, rIdx) => {
            if (row.type === "hunk-header") {
              return (
                <div
                  key={rIdx}
                  style={{
                    padding: "3px 12px",
                    backgroundColor: "rgba(59, 130, 246, 0.12)",
                    color: "#93c5fd",
                    borderTop: "1px solid rgba(59, 130, 246, 0.2)",
                    borderBottom: "1px solid rgba(59, 130, 246, 0.2)",
                    fontSize: "0.78rem",
                  }}
                >
                  {row.hunkHeader}
                </div>
              );
            }

            const left = row.left;
            const right = row.right;

            const isLeftDel = left?.type === "deletion";
            const isRightAdd = right?.type === "addition";

            return (
              <div
                key={rIdx}
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  borderBottom: "1px solid rgba(255, 255, 255, 0.03)",
                }}
              >
                {/* Left side (Before) */}
                <div
                  style={{
                    display: "flex",
                    backgroundColor: isLeftDel
                      ? "rgba(239, 68, 68, 0.18)"
                      : left?.type === "empty"
                      ? "rgba(0, 0, 0, 0.15)"
                      : "transparent",
                    color: isLeftDel ? "#fca5a5" : "var(--text-secondary)",
                    borderRight: "1px solid var(--border-color)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: "44px",
                      flexShrink: 0,
                      padding: "2px 8px",
                      textAlign: "right",
                      userSelect: "none",
                      color: "var(--text-muted)",
                      backgroundColor: "rgba(0, 0, 0, 0.2)",
                      fontSize: "0.75rem",
                    }}
                  >
                    {left?.lineNo ?? ""}
                  </div>
                  <div
                    style={{
                      width: "20px",
                      flexShrink: 0,
                      textAlign: "center",
                      userSelect: "none",
                      color: isLeftDel ? "#ef4444" : "transparent",
                      fontWeight: 700,
                    }}
                  >
                    {isLeftDel ? "-" : ""}
                  </div>
                  <div
                    style={{
                      padding: "2px 8px",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-all",
                      flex: 1,
                    }}
                  >
                    {left?.content}
                  </div>
                </div>

                {/* Right side (After) */}
                <div
                  style={{
                    display: "flex",
                    backgroundColor: isRightAdd
                      ? "rgba(16, 185, 129, 0.18)"
                      : right?.type === "empty"
                      ? "rgba(0, 0, 0, 0.15)"
                      : "transparent",
                    color: isRightAdd ? "#6ee7b7" : "var(--text-secondary)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: "44px",
                      flexShrink: 0,
                      padding: "2px 8px",
                      textAlign: "right",
                      userSelect: "none",
                      color: "var(--text-muted)",
                      backgroundColor: "rgba(0, 0, 0, 0.2)",
                      fontSize: "0.75rem",
                    }}
                  >
                    {right?.lineNo ?? ""}
                  </div>
                  <div
                    style={{
                      width: "20px",
                      flexShrink: 0,
                      textAlign: "center",
                      userSelect: "none",
                      color: isRightAdd ? "#10b981" : "transparent",
                      fontWeight: 700,
                    }}
                  >
                    {isRightAdd ? "+" : ""}
                  </div>
                  <div
                    style={{
                      padding: "2px 8px",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-all",
                      flex: 1,
                    }}
                  >
                    {right?.content}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case "added":
        return (
          <span
            className="badge"
            style={{
              backgroundColor: "rgba(16, 185, 129, 0.15)",
              color: "#34d399",
              border: "1px solid rgba(16, 185, 129, 0.3)",
            }}
          >
            ADDED
          </span>
        );
      case "removed":
        return (
          <span
            className="badge"
            style={{
              backgroundColor: "rgba(239, 68, 68, 0.15)",
              color: "#f87171",
              border: "1px solid rgba(239, 68, 68, 0.3)",
            }}
          >
            REMOVED
          </span>
        );
      case "renamed":
        return (
          <span
            className="badge"
            style={{
              backgroundColor: "rgba(245, 158, 11, 0.15)",
              color: "#fbbf24",
              border: "1px solid rgba(245, 158, 11, 0.3)",
            }}
          >
            RENAMED
          </span>
        );
      default:
        return (
          <span
            className="badge"
            style={{
              backgroundColor: "rgba(59, 130, 246, 0.15)",
              color: "#60a5fa",
              border: "1px solid rgba(59, 130, 246, 0.3)",
            }}
          >
            MODIFIED
          </span>
        );
    }
  };

  const resolvedIssues = changes?.resolved_issues || [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{
          maxWidth: "1060px",
          width: "96%",
          maxHeight: "92vh",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <div
          className="modal-header"
          style={{
            alignItems: "flex-start",
            gap: "1rem",
            flexShrink: 0,
            paddingBottom: "1rem",
            borderBottom: "1px solid var(--border-color)",
          }}
        >
          <div style={{ flex: 1 }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
                marginBottom: "0.5rem",
                flexWrap: "wrap",
              }}
            >
              {isMerged ? (
                <span className="badge badge-merged">
                  <GitMerge size={13} />
                  <span>MERGED</span>
                </span>
              ) : isOpen ? (
                <span className="badge badge-open">
                  <GitPullRequest size={13} />
                  <span>OPEN</span>
                </span>
              ) : (
                <span className="badge badge-closed">
                  <GitPullRequest size={13} />
                  <span>CLOSED</span>
                </span>
              )}

              <span
                style={{
                  fontFamily: "var(--font-mono)",
                  color: "var(--text-muted)",
                  fontSize: "0.9rem",
                }}
              >
                #{pr.pr_number}
              </span>

              {changes && (
                <span
                  style={{
                    fontSize: "0.8rem",
                    color: "var(--text-secondary)",
                    marginLeft: "0.5rem",
                  }}
                >
                  <strong style={{ color: "#34d399" }}>+{changes.total_additions}</strong>{" "}
                  <strong style={{ color: "#f87171" }}>-{changes.total_deletions}</strong> in{" "}
                  {changes.total_files_changed} file{changes.total_files_changed === 1 ? "" : "s"}
                </span>
              )}
            </div>

            <h2
              className="modal-title"
              style={{ fontSize: "1.25rem", lineHeight: 1.4, margin: 0 }}
            >
              {pr.title}
            </h2>
          </div>

          <button className="close-btn" onClick={onClose} title="Close modal">
            <X size={20} />
          </button>
        </div>

        {/* Navigation Sub-Tabs & Diff Controls */}
        <div
          className="tabs-nav"
          style={{
            margin: "0",
            padding: "0.5rem 0",
            borderBottom: "1px solid var(--border-color)",
            flexShrink: 0,
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "0.75rem",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <button
              className={`tab-btn ${activeTab === "diffs" ? "active" : ""}`}
              onClick={() => setActiveTab("diffs")}
            >
              <Columns size={15} />
              <span>Side-by-Side Diffs</span>
              <span
                className="badge badge-label"
                style={{
                  marginLeft: "0.35rem",
                  fontSize: "0.7rem",
                  backgroundColor:
                    activeTab === "diffs"
                      ? "rgba(168, 85, 247, 0.2)"
                      : "var(--bg-card)",
                }}
              >
                {changes ? changes.total_files_changed : "..."}
              </span>
            </button>

            <button
              className={`tab-btn ${activeTab === "overview" ? "active" : ""}`}
              onClick={() => setActiveTab("overview")}
            >
              <GitPullRequest size={15} />
              <span>Overview & Resolved Issues</span>
              {resolvedIssues.length > 0 && (
                <span
                  className="badge"
                  style={{
                    backgroundColor: "rgba(16, 185, 129, 0.2)",
                    color: "#34d399",
                    fontSize: "0.7rem",
                    marginLeft: "0.35rem",
                  }}
                >
                  {resolvedIssues.length} fixed
                </span>
              )}
            </button>

            <button
              className={`tab-btn ${activeTab === "commits" ? "active" : ""}`}
              onClick={() => setActiveTab("commits")}
            >
              <GitCommit size={15} />
              <span>Commits</span>
              <span
                className="badge badge-label"
                style={{
                  marginLeft: "0.35rem",
                  fontSize: "0.7rem",
                  backgroundColor:
                    activeTab === "commits"
                      ? "rgba(59, 130, 246, 0.2)"
                      : "var(--bg-card)",
                }}
              >
                {changes ? changes.total_commits : "..."}
              </span>
            </button>
          </div>

          {/* Right side controls: Side-by-side / Unified mode toggle + Sync */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            {activeTab === "diffs" && (
              <div
                style={{
                  display: "inline-flex",
                  backgroundColor: "var(--bg-primary)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-color)",
                  padding: "2px",
                }}
              >
                <button
                  onClick={() => setDiffMode("split")}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.35rem",
                    padding: "3px 8px",
                    fontSize: "0.75rem",
                    fontWeight: 500,
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer",
                    backgroundColor:
                      diffMode === "split" ? "var(--bg-card)" : "transparent",
                    color:
                      diffMode === "split"
                        ? "var(--text-primary)"
                        : "var(--text-muted)",
                  }}
                  title="Show Side-by-Side (Split) comparison"
                >
                  <Columns size={13} />
                  <span>Split (Side-by-Side)</span>
                </button>

                <button
                  onClick={() => setDiffMode("unified")}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.35rem",
                    padding: "3px 8px",
                    fontSize: "0.75rem",
                    fontWeight: 500,
                    border: "none",
                    borderRadius: "4px",
                    cursor: "pointer",
                    backgroundColor:
                      diffMode === "unified" ? "var(--bg-card)" : "transparent",
                    color:
                      diffMode === "unified"
                        ? "var(--text-primary)"
                        : "var(--text-muted)",
                  }}
                  title="Show Unified (Inline) diff"
                >
                  <List size={13} />
                  <span>Unified</span>
                </button>
              </div>
            )}

            <button
              className="btn btn-secondary btn-sm"
              onClick={handleForceSyncDiffs}
              disabled={syncingChanges || loadingChanges}
              title="Force re-sync commits and code diffs from GitHub"
              style={{ fontSize: "0.75rem", padding: "3px 8px" }}
            >
              {syncingChanges ? (
                <>
                  <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />
                  <span>Syncing...</span>
                </>
              ) : (
                <>
                  <RefreshCw size={12} />
                  <span>Sync Diffs</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Error alert */}
        {error && (
          <div className="alert alert-danger" style={{ margin: "1rem 0" }}>
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Modal Scrollable Body */}
        <div style={{ flex: 1, overflowY: "auto", padding: "1.25rem 0" }}>
          {/* TAB 1: SIDE-BY-SIDE / CHANGED FILES & DIFFS */}
          {activeTab === "diffs" && (
            <div>
              {/* Resolved Issues Notice Banner in Diffs Tab */}
              {resolvedIssues.length > 0 && (
                <div
                  style={{
                    marginBottom: "1.25rem",
                    padding: "0.85rem 1.15rem",
                    backgroundColor: "rgba(16, 185, 129, 0.1)",
                    border: "1px solid rgba(16, 185, 129, 0.3)",
                    borderRadius: "var(--radius-md)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    flexWrap: "wrap",
                    gap: "0.75rem",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                    <CheckCircle2 size={18} color="#34d399" />
                    <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "#6ee7b7" }}>
                      This PR addresses & resolves:
                    </span>
                    <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                      {resolvedIssues.map((ri) => (
                        <button
                          key={ri.issue_number}
                          onClick={() => handleInspectIssue(ri)}
                          disabled={openingIssueNum === ri.issue_number}
                          className="badge"
                          style={{
                            backgroundColor: "rgba(16, 185, 129, 0.25)",
                            color: "#34d399",
                            border: "1px solid rgba(16, 185, 129, 0.5)",
                            cursor: onSelectIssue ? "pointer" : "default",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.3rem",
                            fontSize: "0.78rem",
                            padding: "3px 8px",
                          }}
                          title={`Click to view Issue #${ri.issue_number}`}
                        >
                          {openingIssueNum === ri.issue_number ? (
                            <Loader2 size={11} style={{ animation: "spin 1s linear infinite" }} />
                          ) : (
                            <Wrench size={11} />
                          )}
                          <span>#{ri.issue_number}: {ri.title}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {loadingChanges ? (
                <div style={{ textAlign: "center", padding: "3rem 1rem" }}>
                  <div className="spinner" style={{ margin: "0 auto 1rem auto" }} />
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem" }}>
                    Fetching side-by-side differences...
                  </p>
                </div>
              ) : changes && changes.files.length > 0 ? (
                <div>
                  {/* Summary bar */}
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      backgroundColor: "var(--bg-primary)",
                      padding: "0.75rem 1rem",
                      borderRadius: "var(--radius-sm)",
                      border: "1px solid var(--border-color)",
                      marginBottom: "1rem",
                      fontSize: "0.85rem",
                    }}
                  >
                    <span style={{ color: "var(--text-secondary)" }}>
                      Showing{" "}
                      <strong style={{ color: "var(--text-primary)" }}>
                        {changes.total_files_changed}
                      </strong>{" "}
                      changed file{changes.total_files_changed === 1 ? "" : "s"}
                    </span>

                    <div style={{ display: "flex", gap: "0.75rem" }}>
                      <span style={{ color: "#34d399", fontWeight: 600 }}>
                        +{changes.total_additions} lines
                      </span>
                      <span style={{ color: "#f87171", fontWeight: 600 }}>
                        -{changes.total_deletions} lines
                      </span>
                    </div>
                  </div>

                  {/* List of files with diffs */}
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    {changes.files.map((file: CodeDiff) => {
                      const isExpanded = !!expandedFiles[file.id];
                      return (
                        <div
                          key={file.id}
                          className="card"
                          style={{
                            padding: 0,
                            overflow: "hidden",
                            border: "1px solid var(--border-color)",
                          }}
                        >
                          {/* File Header */}
                          <div
                            onClick={() => toggleFileExpansion(file.id)}
                            style={{
                              padding: "0.75rem 1rem",
                              backgroundColor: "rgba(31, 41, 55, 0.4)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              cursor: "pointer",
                              userSelect: "none",
                              borderBottom: isExpanded ? "1px solid var(--border-color)" : "none",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                              {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                              {getStatusBadge(file.status)}
                              <span
                                style={{
                                  fontFamily: "var(--font-mono)",
                                  fontWeight: 600,
                                  fontSize: "0.85rem",
                                  color: "var(--text-primary)",
                                }}
                              >
                                {file.filename}
                              </span>
                              {file.previous_filename && (
                                <span
                                  style={{
                                    fontSize: "0.75rem",
                                    color: "var(--text-muted)",
                                    fontStyle: "italic",
                                  }}
                                >
                                  (from {file.previous_filename})
                                </span>
                              )}
                            </div>

                            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                              <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                                <strong style={{ color: "#34d399" }}>+{file.additions}</strong>{" "}
                                <strong style={{ color: "#f87171" }}>-{file.deletions}</strong>
                              </span>

                              {file.raw_url && (
                                <a
                                  href={file.raw_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  onClick={(e) => e.stopPropagation()}
                                  className="btn btn-secondary btn-sm"
                                  style={{ padding: "2px 6px" }}
                                  title="View raw file on GitHub"
                                >
                                  <ExternalLink size={12} />
                                </a>
                              )}
                            </div>
                          </div>

                          {/* File Diff Content: Split vs Unified */}
                          {isExpanded && (
                            <div
                              style={{
                                backgroundColor: "var(--bg-primary)",
                                maxHeight: "500px",
                                overflowY: "auto",
                              }}
                            >
                              {file.diff_content ? (
                                diffMode === "split" ? (
                                  renderSplitDiffTable(file.diff_content)
                                ) : (
                                  <div style={{ padding: "0.5rem 0" }}>
                                    {file.diff_content
                                      .split("\n")
                                      .map((line, lIdx) => renderUnifiedLine(line, lIdx))}
                                  </div>
                                )
                              ) : (
                                <div
                                  style={{
                                    padding: "1.5rem",
                                    color: "var(--text-muted)",
                                    fontStyle: "italic",
                                    fontSize: "0.825rem",
                                    textAlign: "center",
                                  }}
                                >
                                  Binary file or diff not available in patch.
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="empty-state" style={{ padding: "3rem 1rem" }}>
                  <Columns size={40} className="empty-state-icon" />
                  <h4 className="empty-state-title">No Code Diffs Ingested Yet</h4>
                  <p className="empty-state-desc">
                    Click "Sync Diffs" in the top bar to fetch the changed files and unified diff patches from GitHub.
                  </p>
                  <button className="btn btn-primary btn-sm" onClick={handleForceSyncDiffs}>
                    <RefreshCw size={13} />
                    <span>Sync Code Diffs Now</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: OVERVIEW & RESOLVED ISSUES */}
          {activeTab === "overview" && (
            <div>
              {/* Resolved Issues Section */}
              <div
                style={{
                  marginBottom: "1.5rem",
                  padding: "1.25rem",
                  backgroundColor: "rgba(16, 185, 129, 0.08)",
                  border: "1px solid rgba(16, 185, 129, 0.25)",
                  borderRadius: "var(--radius-md)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    marginBottom: "0.75rem",
                  }}
                >
                  <CheckCircle2 size={18} color="#34d399" />
                  <h4
                    style={{
                      fontSize: "0.95rem",
                      fontWeight: 700,
                      color: "#6ee7b7",
                      margin: 0,
                    }}
                  >
                    Issues Resolved & Addressed by this PR
                  </h4>
                </div>

                {resolvedIssues.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    {resolvedIssues.map((ri) => (
                      <div
                        key={ri.issue_number}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "0.6rem 0.85rem",
                          backgroundColor: "var(--bg-secondary)",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--border-color)",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                          <span
                            className="badge badge-label"
                            style={{
                              backgroundColor: "rgba(16, 185, 129, 0.2)",
                              color: "#34d399",
                              fontFamily: "var(--font-mono)",
                            }}
                          >
                            #{ri.issue_number}
                          </span>
                          <span style={{ fontWeight: 600, fontSize: "0.875rem" }}>
                            {ri.title}
                          </span>
                          <span
                            className={`badge ${
                              ri.state.toLowerCase() === "closed" ? "badge-closed" : "badge-open"
                            }`}
                            style={{ fontSize: "0.7rem" }}
                          >
                            {ri.state.toUpperCase()}
                          </span>
                        </div>

                        <div style={{ display: "flex", gap: "0.5rem" }}>
                          {onSelectIssue && ri.id > 0 && (
                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleInspectIssue(ri)}
                              disabled={openingIssueNum === ri.issue_number}
                              style={{
                                fontSize: "0.75rem",
                                color: "#93c5fd",
                                borderColor: "rgba(59, 130, 246, 0.4)",
                              }}
                            >
                              {openingIssueNum === ri.issue_number ? (
                                <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />
                              ) : (
                                <Wrench size={12} />
                              )}
                              <span>Inspect Issue & Solution</span>
                            </button>
                          )}

                          {ri.html_url && (
                            <a
                              href={ri.html_url}
                              target="_blank"
                              rel="noreferrer"
                              className="btn btn-secondary btn-sm"
                              style={{ padding: "3px 6px" }}
                              title="Open on GitHub"
                            >
                              <ExternalLink size={12} />
                            </a>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-secondary)",
                      margin: 0,
                    }}
                  >
                    No specific issue links detected in this PR's description or commit messages. You can reference issues using keywords like <code>Fixes #123</code> or <code>Resolves #123</code>.
                  </p>
                )}
              </div>

              {/* Metadata row */}
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "1.25rem",
                  paddingBottom: "1rem",
                  fontSize: "0.85rem",
                  color: "var(--text-secondary)",
                  borderBottom: "1px solid var(--border-color)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <User size={15} color="var(--text-muted)" />
                  <span>Author:</span>
                  <strong style={{ color: "var(--text-primary)" }}>
                    {pr.author || "Unknown"}
                  </strong>
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                  <Calendar size={15} color="var(--text-muted)" />
                  <span>Created:</span>
                  <span style={{ color: "var(--text-primary)" }}>
                    {new Date(pr.created_at).toLocaleDateString()}
                  </span>
                </div>

                {pr.merged_at && (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <GitMerge size={15} color="#c084fc" />
                    <span>Merged:</span>
                    <span style={{ color: "#c084fc", fontWeight: 500 }}>
                      {new Date(pr.merged_at).toLocaleDateString()}
                    </span>
                  </div>
                )}

                {pr.closed_at && !pr.merged_at && (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <span>Closed:</span>
                    <span style={{ color: "var(--text-muted)" }}>
                      {new Date(pr.closed_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
              </div>

              {/* Action buttons */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  padding: "0.85rem 0",
                  flexWrap: "wrap",
                  borderBottom: "1px solid var(--border-color)",
                }}
              >
                {pr.html_url && (
                  <a
                    href={pr.html_url}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-secondary btn-sm"
                  >
                    <ExternalLink size={14} />
                    <span>Open on GitHub</span>
                  </a>
                )}

                {pr.diff_url && (
                  <a
                    href={pr.diff_url}
                    target="_blank"
                    rel="noreferrer"
                    className="btn btn-secondary btn-sm"
                    style={{
                      borderColor: "rgba(59, 130, 246, 0.4)",
                      color: "#93c5fd",
                    }}
                  >
                    <FileCode size={14} />
                    <span>View Raw Diff (.diff)</span>
                  </a>
                )}

                <button className="btn btn-secondary btn-sm" onClick={handleCopyLink}>
                  {copiedLink ? <Check size={14} color="#34d399" /> : <Copy size={14} />}
                  <span>{copiedLink ? "Copied!" : "Copy PR URL"}</span>
                </button>
              </div>

              {/* Labels */}
              {pr.labels && pr.labels.length > 0 && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.5rem",
                    padding: "0.75rem 0",
                    flexWrap: "wrap",
                    borderBottom: "1px solid var(--border-color)",
                  }}
                >
                  <Tag size={14} color="var(--text-muted)" />
                  {pr.labels.map((lbl, idx) => {
                    const name = typeof lbl === "string" ? lbl : lbl.name;
                    const color =
                      typeof lbl === "string" ? "4b5563" : lbl.color || "4b5563";
                    return (
                      <span
                        key={idx}
                        className="badge badge-label"
                        style={{
                          backgroundColor: `#${color}25`,
                          color: `#${color}`,
                          borderColor: `#${color}60`,
                        }}
                      >
                        {name}
                      </span>
                    );
                  })}
                </div>
              )}

              {/* Description Body */}
              <div style={{ marginTop: "1rem" }}>
                <h4
                  style={{
                    fontSize: "0.85rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    color: "var(--text-muted)",
                    marginBottom: "0.75rem",
                    fontWeight: 600,
                  }}
                >
                  Pull Request Description
                </h4>

                {pr.body && pr.body.trim() ? (
                  <div
                    style={{
                      backgroundColor: "var(--bg-primary)",
                      border: "1px solid var(--border-color)",
                      borderRadius: "var(--radius-sm)",
                      padding: "1.25rem",
                      color: "var(--text-primary)",
                      fontSize: "0.9rem",
                      lineHeight: 1.6,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {pr.body}
                  </div>
                ) : (
                  <p
                    style={{
                      fontStyle: "italic",
                      color: "var(--text-muted)",
                      fontSize: "0.875rem",
                    }}
                  >
                    No description provided for this pull request.
                  </p>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: COMMITS */}
          {activeTab === "commits" && (
            <div>
              {loadingChanges ? (
                <div style={{ textAlign: "center", padding: "2rem" }}>
                  <div className="spinner" style={{ margin: "0 auto 1rem auto" }} />
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>
                    Loading pull request commits...
                  </p>
                </div>
              ) : changes && changes.commits.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  {changes.commits.map((c) => (
                    <div
                      key={c.id}
                      className="card"
                      style={{
                        padding: "0.85rem 1.15rem",
                        display: "flex",
                        alignItems: "flex-start",
                        justifyContent: "space-between",
                        gap: "1rem",
                      }}
                    >
                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            gap: "0.5rem",
                            marginBottom: "0.35rem",
                          }}
                        >
                          <GitCommit size={15} color="var(--accent-primary)" />
                          <span
                            style={{
                              fontWeight: 600,
                              fontSize: "0.9rem",
                              color: "var(--text-primary)",
                            }}
                          >
                            {c.message.split("\n")[0]}
                          </span>
                        </div>

                        {c.message.includes("\n") && (
                          <p
                            style={{
                              fontSize: "0.8rem",
                              color: "var(--text-secondary)",
                              marginBottom: "0.35rem",
                              whiteSpace: "pre-wrap",
                            }}
                          >
                            {c.message.split("\n").slice(1).join("\n").trim()}
                          </p>
                        )}

                        <div
                          style={{
                            fontSize: "0.78rem",
                            color: "var(--text-muted)",
                            display: "flex",
                            gap: "0.85rem",
                            flexWrap: "wrap",
                          }}
                        >
                          <span>By: <strong style={{ color: "var(--text-secondary)" }}>{c.author_name || "Unknown"}</strong></span>
                          {c.committed_at && (
                            <span>{new Date(c.committed_at).toLocaleString()}</span>
                          )}
                        </div>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <span
                          style={{
                            fontFamily: "var(--font-mono)",
                            fontSize: "0.78rem",
                            backgroundColor: "var(--bg-primary)",
                            padding: "2px 6px",
                            borderRadius: "4px",
                            border: "1px solid var(--border-color)",
                            color: "#93c5fd",
                          }}
                        >
                          {c.sha.slice(0, 7)}
                        </span>
                        {c.html_url && (
                          <a
                            href={c.html_url}
                            target="_blank"
                            rel="noreferrer"
                            className="btn btn-secondary btn-sm"
                            style={{ padding: "2px 6px" }}
                            title="Open commit on GitHub"
                          >
                            <ExternalLink size={12} />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state" style={{ padding: "2.5rem 1rem" }}>
                  <GitCommit size={36} className="empty-state-icon" />
                  <h4 className="empty-state-title">No Commits Ingested Yet</h4>
                  <p className="empty-state-desc">
                    Click "Sync Diffs" in the top bar to pull commit history directly from GitHub.
                  </p>
                  <button className="btn btn-primary btn-sm" onClick={handleForceSyncDiffs}>
                    <RefreshCw size={13} />
                    <span>Sync Commits Now</span>
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
