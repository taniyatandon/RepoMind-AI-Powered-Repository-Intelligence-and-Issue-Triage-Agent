import React, { useEffect, useMemo, useState } from "react";
import {
  apiDiagnoseIssue,
  apiGetIssueAnalysis,
  apiGetRepositoryIssues,
  apiGetRepositoryLabels,
  apiGetRepositoryPullRequests,
  apiTriageAllRepoIssues,
} from "../api";
import { Issue, IssueAnalysis, PaginatedIssues, Repository } from "../types";
import { PullRequestExplorer } from "./PullRequestExplorer";
import {
  AlertCircle,
  ArrowLeft,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleDot,
  Code2,
  Columns,
  Copy,
  Cpu,
  ExternalLink,
  FileCode,
  Filter,
  GitFork,
  GitPullRequest,
  LayoutGrid,
  Lightbulb,
  Loader2,
  Maximize2,
  MessageSquare,
  RefreshCw,
  Search,
  Sparkles,
  Star,
  Tag,
  Terminal,
  Wrench,
  X,
} from "lucide-react";

interface IssueExplorerProps {
  repository: Repository;
  onBack: () => void;
  onSelectIssue: (issue: Issue) => void;
  onSyncRepo?: () => void;
  initialTab?: "issues" | "pulls";
  onTabChange?: (tab: "issues" | "pulls") => void;
}

export const IssueExplorer: React.FC<IssueExplorerProps> = ({
  repository,
  onBack,
  onSelectIssue,
  onSyncRepo,
  initialTab = "issues",
  onTabChange,
}) => {
  const [viewMode, setViewMode] = useState<"workspace" | "table">("workspace");
  const [activeTab, setActiveTab] = useState<"issues" | "pulls">(initialTab);

  useEffect(() => {
    if (initialTab && initialTab !== activeTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);
  const [prCount, setPrCount] = useState<number | null>(null);
  const [issuesData, setIssuesData] = useState<PaginatedIssues>({
    items: [],
    total: 0,
    page: 1,
    per_page: 10,
    total_pages: 1,
  });
  const [labels, setLabels] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triagingAll, setTriagingAll] = useState(false);
  const [triageMessage, setTriageMessage] = useState<string | null>(null);

  // Selected issue inside the 3-panel workspace
  const [selectedIssueItem, setSelectedIssueItem] = useState<Issue | null>(null);
  const [inlineAnalysis, setInlineAnalysis] = useState<IssueAnalysis | null>(null);
  const [loadingInlineAnalysis, setLoadingInlineAnalysis] = useState(false);
  const [diagnosingInline, setDiagnosingInline] = useState(false);
  const [copiedPatch, setCopiedPatch] = useState(false);
  const [copiedTest, setCopiedTest] = useState(false);

  // Filters state
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedLabel, setSelectedLabel] = useState<string>("all");
  const [titleSearch, setTitleSearch] = useState<string>("");

  const handleBatchTriage = async () => {
    setTriagingAll(true);
    setTriageMessage(null);
    try {
      const res = await apiTriageAllRepoIssues(repository.id);
      setTriageMessage(res.message);
      setTimeout(() => setTriageMessage(null), 5000);
      // Reload active issue analysis if present
      if (selectedIssueItem) {
        loadIssueAnalysis(selectedIssueItem.id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to batch triage repository issues.");
    } finally {
      setTriagingAll(false);
    }
  };

  // Load repository labels on mount
  useEffect(() => {
    async function loadLabels() {
      try {
        const repoLabels = await apiGetRepositoryLabels(repository.id);
        setLabels(repoLabels);
      } catch (err) {
        console.warn("Could not load repo labels:", err);
      }
    }
    loadLabels();
  }, [repository.id]);

  // Load repository PR count on mount
  useEffect(() => {
    async function loadPrCount() {
      try {
        const prs = await apiGetRepositoryPullRequests(repository.id, { page: 1, per_page: 1 });
        setPrCount(prs.total);
      } catch (err) {
        console.warn("Could not load repo PR count:", err);
      }
    }
    loadPrCount();
  }, [repository.id]);

  // Load issues whenever filter/pagination changes
  useEffect(() => {
    let isCancelled = false;

    async function loadIssues() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiGetRepositoryIssues(repository.id, {
          page,
          per_page: perPage,
          status: statusFilter,
          label: selectedLabel,
          title: titleSearch,
        });
        if (!isCancelled) {
          setIssuesData(data);
          // If in workspace view and no issue is currently selected, select the first one
          if (data.items.length > 0 && !selectedIssueItem) {
            setSelectedIssueItem(data.items[0]);
          }
        }
      } catch (err: any) {
        if (!isCancelled) {
          setError(err.message || "Failed to load issues.");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    loadIssues();
    return () => {
      isCancelled = true;
    };
  }, [repository.id, page, perPage, statusFilter, selectedLabel, titleSearch]);

  // Load analysis whenever selected issue changes
  const loadIssueAnalysis = async (issueId: number) => {
    setLoadingInlineAnalysis(true);
    setInlineAnalysis(null);
    try {
      const data = await apiGetIssueAnalysis(issueId);
      setInlineAnalysis(data);
    } catch {
      // Not yet analyzed or analysis missing
      setInlineAnalysis(null);
    } finally {
      setLoadingInlineAnalysis(false);
    }
  };

  useEffect(() => {
    if (selectedIssueItem) {
      loadIssueAnalysis(selectedIssueItem.id);
    } else {
      setInlineAnalysis(null);
    }
  }, [selectedIssueItem]);

  const handleRunInlineDiagnosis = async () => {
    if (!selectedIssueItem) return;
    setDiagnosingInline(true);
    try {
      const result = await apiDiagnoseIssue(selectedIssueItem.id);
      setInlineAnalysis(result);
    } catch (err: any) {
      setError(err.message || "Failed to diagnose issue.");
    } finally {
      setDiagnosingInline(false);
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

  const handleResetFilters = () => {
    setStatusFilter("all");
    setSelectedLabel("all");
    setTitleSearch("");
    setPage(1);
  };

  const hasActiveFilters =
    statusFilter !== "all" || selectedLabel !== "all" || titleSearch.trim() !== "";

  // Real-data analytics summary computed from current issues
  const { openPercent } = useMemo(() => {
    const total = issuesData.total || 0;
    const items = issuesData.items || [];
    const openInPage = items.filter((i) => i.state.toLowerCase() === "open").length;

    let estOpen = openInPage;
    if (items.length > 0 && total > items.length) {
      const ratio = openInPage / items.length;
      estOpen = Math.round(total * ratio);
    }
    const pct = total > 0 ? Math.round((estOpen / total) * 100) : 50;
    return { openPercent: pct };
  }, [issuesData]);

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
          padding: "2px 8px",
          backgroundColor: bg,
          color: color,
          fontFamily: "var(--font-mono)",
          fontSize: "0.8rem",
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
    <div>
      {/* Top Header & Navigation Bar */}
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
        <button
          className="btn btn-secondary btn-sm"
          onClick={onBack}
          style={{ gap: "0.4rem" }}
        >
          <ArrowLeft size={14} />
          <span>All Repositories</span>
        </button>

        <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
          {/* View Mode Toggle: 3-Panel Workspace vs Full Table */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              backgroundColor: "rgba(255, 255, 255, 0.04)",
              borderRadius: "var(--radius-sm)",
              padding: "2px",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <button
              onClick={() => setViewMode("workspace")}
              style={{
                padding: "3px 8px",
                border: "none",
                background: viewMode === "workspace" ? "var(--bg-elevated)" : "transparent",
                color: viewMode === "workspace" ? "#ffffff" : "var(--text-muted)",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "0.75rem",
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
              }}
              title="3-Panel Developer Workspace"
            >
              <Columns size={13} />
              <span>Workspace</span>
            </button>

            <button
              onClick={() => setViewMode("table")}
              style={{
                padding: "3px 8px",
                border: "none",
                background: viewMode === "table" ? "var(--bg-elevated)" : "transparent",
                color: viewMode === "table" ? "#ffffff" : "var(--text-muted)",
                borderRadius: "4px",
                cursor: "pointer",
                fontSize: "0.75rem",
                fontWeight: 600,
                display: "inline-flex",
                alignItems: "center",
                gap: "0.3rem",
              }}
              title="Full Data Table View"
            >
              <LayoutGrid size={13} />
              <span>Table</span>
            </button>
          </div>

          {onSyncRepo && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={onSyncRepo}
              title="Sync latest GitHub metadata, issues & PRs"
            >
              <RefreshCw size={13} />
              <span>Sync</span>
            </button>
          )}

          <a
            href={repository.html_url}
            target="_blank"
            rel="noreferrer"
            className="btn btn-secondary btn-sm"
            style={{ textDecoration: "none" }}
          >
            <span>GitHub</span>
            <ExternalLink size={13} />
          </a>
        </div>
      </div>

      {/* Repository Command Header Card */}
      <div
        className="card"
        style={{
          padding: "1.25rem 1.5rem",
          marginBottom: "1.25rem",
          border: "1px solid var(--border-color)",
          boxShadow: "var(--shadow-md)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "1rem",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
              <h1 style={{ fontSize: "1.4rem", fontWeight: 800, letterSpacing: "-0.025em" }}>
                {repository.full_name}
              </h1>

              {repository.language && (
                <span
                  className="badge badge-label"
                  style={{
                    backgroundColor: "rgba(99, 102, 241, 0.12)",
                    color: "#a5b4fc",
                    borderColor: "rgba(99, 102, 241, 0.3)",
                    fontWeight: 600,
                  }}
                >
                  {repository.language}
                </span>
              )}

              <span style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                <Star size={13} color="#f59e0b" fill="#f59e0b" />
                {repository.stargazers_count.toLocaleString()}
              </span>

              <span style={{ display: "inline-flex", alignItems: "center", gap: "0.3rem", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                <GitFork size={13} color="var(--text-muted)" />
                {repository.forks_count.toLocaleString()}
              </span>
            </div>

            {repository.description && (
              <p
                style={{
                  color: "var(--text-secondary)",
                  fontSize: "0.85rem",
                  marginTop: "0.35rem",
                  maxWidth: "780px",
                  lineHeight: 1.5,
                }}
              >
                {repository.description}
              </p>
            )}
          </div>

          {/* AI Batch Action */}
          <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
            <button
              className="btn btn-primary btn-sm"
              onClick={handleBatchTriage}
              disabled={triagingAll || issuesData.total === 0}
              style={{
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                boxShadow: "0 0 16px rgba(139, 92, 246, 0.35)",
              }}
            >
              {triagingAll ? (
                <>
                  <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />
                  <span>Diagnosing...</span>
                </>
              ) : (
                <>
                  <Sparkles size={14} />
                  <span>Batch AI Triage</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Real Data Telemetry Strip */}
        <div
          style={{
            marginTop: "1rem",
            paddingTop: "0.85rem",
            borderTop: "1px solid var(--border-subtle)",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
            gap: "1.25rem",
            alignItems: "center",
          }}
        >
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.725rem", color: "var(--text-secondary)", marginBottom: "0.35rem" }}>
              <span>State Distribution</span>
              <span style={{ fontFamily: "var(--font-mono)" }}>
                {issuesData.total > 0 ? `${openPercent}% Open` : "No issues"}
              </span>
            </div>
            <div
              style={{
                width: "100%",
                height: "6px",
                borderRadius: "3px",
                backgroundColor: "rgba(239, 68, 68, 0.3)",
                overflow: "hidden",
                display: "flex",
              }}
            >
              <div
                style={{
                  width: `${openPercent}%`,
                  height: "100%",
                  backgroundColor: "#10b981",
                  transition: "width 0.3s ease",
                }}
              />
            </div>
          </div>

          <div style={{ display: "flex", gap: "1.25rem", fontSize: "0.775rem", color: "var(--text-secondary)" }}>
            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", display: "block" }}>ISSUES INDEXED</span>
              <strong style={{ fontSize: "0.95rem", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                {issuesData.total}
              </strong>
            </div>

            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", display: "block" }}>PULL REQUESTS</span>
              <strong style={{ fontSize: "0.95rem", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                {prCount !== null ? prCount : "—"}
              </strong>
            </div>

            <div>
              <span style={{ color: "var(--text-muted)", fontSize: "0.7rem", display: "block" }}>LABELS IDENTIFIED</span>
              <strong style={{ fontSize: "0.95rem", color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                {labels.length}
              </strong>
            </div>
          </div>
        </div>
      </div>

      {/* Triage feedback message */}
      {triageMessage && (
        <div className="alert alert-success">
          <Sparkles size={16} style={{ flexShrink: 0, marginTop: "2px" }} />
          <div>{triageMessage}</div>
        </div>
      )}

      {/* Error alert */}
      {error && (
        <div className="alert alert-danger">
          <AlertCircle size={16} style={{ flexShrink: 0, marginTop: "2px" }} />
          <div>{error}</div>
        </div>
      )}

      {/* View Tabs: Issues vs Pull Requests */}
      <div className="tabs-nav">
        <button
          className={`tab-btn ${activeTab === "issues" ? "active" : ""}`}
          onClick={() => {
            setActiveTab("issues");
            onTabChange?.("issues");
          }}
        >
          <CircleDot size={16} color={activeTab === "issues" ? "#818cf8" : "currentColor"} />
          <span>Issues & AI Triage</span>
          <span
            className="badge badge-label"
            style={{
              marginLeft: "0.35rem",
              fontSize: "0.7rem",
              backgroundColor:
                activeTab === "issues"
                  ? "rgba(99, 102, 241, 0.2)"
                  : "rgba(255, 255, 255, 0.05)",
              color: activeTab === "issues" ? "#a5b4fc" : "var(--text-secondary)",
            }}
          >
            {issuesData.total}
          </span>
        </button>

        <button
          className={`tab-btn ${activeTab === "pulls" ? "active" : ""}`}
          onClick={() => {
            setActiveTab("pulls");
            onTabChange?.("pulls");
          }}
        >
          <GitPullRequest size={16} color={activeTab === "pulls" ? "#c084fc" : "currentColor"} />
          <span>Pull Requests & Diffs</span>
          {prCount !== null && (
            <span
              className="badge badge-label"
              style={{
                marginLeft: "0.35rem",
                fontSize: "0.7rem",
                backgroundColor:
                  activeTab === "pulls"
                    ? "rgba(168, 85, 247, 0.2)"
                    : "rgba(255, 255, 255, 0.05)",
                color: activeTab === "pulls" ? "#c084fc" : "var(--text-secondary)",
              }}
            >
              {prCount}
            </span>
          )}
        </button>
      </div>

      {/* If Pull Requests tab is active, render PullRequestExplorer */}
      {activeTab === "pulls" && (
        <PullRequestExplorer
          repository={repository}
          onSyncRepo={onSyncRepo}
          onSelectIssue={onSelectIssue}
        />
      )}

      {/* If Issues tab is active: */}
      {activeTab === "issues" && (
        <>
          {/* ====================================================================
              MODE 1: 3-PANEL STRUCTURED DEVELOPER WORKSPACE (Centerpiece)
              ==================================================================== */}
          {viewMode === "workspace" ? (
            <div className="workspace-3panel-container">
              {/* LEFT PANEL: REPOSITORY EXPLORER */}
              <div className="workspace-panel-left">
                <div className="workspace-panel-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--text-primary)" }}>
                      Issues Explorer
                    </span>
                    <span className="badge badge-label" style={{ fontSize: "0.65rem" }}>
                      {issuesData.total}
                    </span>
                  </div>

                  {hasActiveFilters && (
                    <button
                      onClick={handleResetFilters}
                      style={{
                        background: "none",
                        border: "none",
                        color: "#818cf8",
                        fontSize: "0.725rem",
                        cursor: "pointer",
                      }}
                    >
                      Clear
                    </button>
                  )}
                </div>

                {/* Left Panel Search & Status Filters */}
                <div style={{ padding: "0.6rem 0.75rem", borderBottom: "1px solid var(--border-subtle)", display: "flex", gap: "0.4rem" }}>
                  <div style={{ position: "relative", flex: 1 }}>
                    <input
                      type="text"
                      className="form-input"
                      style={{
                        paddingLeft: "1.9rem",
                        paddingRight: titleSearch ? "1.5rem" : "0.5rem",
                        fontSize: "0.775rem",
                        height: "32px",
                      }}
                      placeholder="Filter issues..."
                      value={titleSearch}
                      onChange={(e) => {
                        setTitleSearch(e.target.value);
                        setPage(1);
                      }}
                    />
                    <Search
                      size={12}
                      style={{
                        position: "absolute",
                        left: "0.65rem",
                        top: "50%",
                        transform: "translateY(-50%)",
                        color: "var(--text-muted)",
                      }}
                    />
                    {titleSearch && (
                      <button
                        onClick={() => setTitleSearch("")}
                        style={{
                          position: "absolute",
                          right: "0.4rem",
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "none",
                          border: "none",
                          color: "var(--text-muted)",
                          cursor: "pointer",
                        }}
                      >
                        <X size={12} />
                      </button>
                    )}
                  </div>

                  <select
                    className="form-select"
                    style={{ width: "auto", fontSize: "0.75rem", height: "32px", paddingRight: "1.8rem" }}
                    value={statusFilter}
                    onChange={(e) => {
                      setStatusFilter(e.target.value);
                      setPage(1);
                    }}
                  >
                    <option value="all">All</option>
                    <option value="open">Open</option>
                    <option value="closed">Closed</option>
                  </select>
                </div>

                {/* Left Panel Issue Items List */}
                <div style={{ flex: 1, overflowY: "auto", scrollbarWidth: "thin" }}>
                  {loading && (
                    <div style={{ padding: "2rem 1rem", textAlign: "center" }}>
                      <div className="spinner spinner-sm" style={{ margin: "0 auto 0.5rem auto" }} />
                      <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Loading issues...</span>
                    </div>
                  )}

                  {!loading && issuesData.items.length === 0 && (
                    <div style={{ padding: "2rem 1rem", textAlign: "center", color: "var(--text-muted)", fontSize: "0.8rem" }}>
                      No issues found.
                    </div>
                  )}

                  {!loading &&
                    issuesData.items.map((issue) => {
                      const isSelected = selectedIssueItem?.id === issue.id;
                      const isOpen = issue.state.toLowerCase() === "open";

                      return (
                        <div
                          key={issue.id}
                          className={`workspace-issue-item ${isSelected ? "active" : ""}`}
                          onClick={() => setSelectedIssueItem(issue)}
                        >
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "0.4rem", marginBottom: "0.25rem" }}>
                            <span
                              style={{
                                fontFamily: "var(--font-mono)",
                                fontSize: "0.75rem",
                                color: isSelected ? "#a5b4fc" : "var(--text-muted)",
                                fontWeight: 600,
                              }}
                            >
                              #{issue.issue_number}
                            </span>
                            <span
                              className={`badge ${isOpen ? "badge-open" : "badge-closed"}`}
                              style={{ fontSize: "0.65rem", padding: "1px 5px" }}
                            >
                              {issue.state.toUpperCase()}
                            </span>
                          </div>

                          <div
                            style={{
                              fontSize: "0.825rem",
                              fontWeight: isSelected ? 600 : 500,
                              color: isSelected ? "#ffffff" : "var(--text-primary)",
                              lineHeight: 1.35,
                              marginBottom: "0.35rem",
                              display: "-webkit-box",
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: "vertical",
                              overflow: "hidden",
                            }}
                          >
                            {issue.title}
                          </div>

                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.725rem", color: "var(--text-muted)" }}>
                            <span style={{ maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {issue.author || "Unknown"}
                            </span>
                            <span style={{ display: "inline-flex", alignItems: "center", gap: "0.2rem" }}>
                              <MessageSquare size={11} />
                              {issue.comments_count}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                </div>

                {/* Left Panel Pagination Controls */}
                <div
                  style={{
                    padding: "0.6rem 0.75rem",
                    borderTop: "1px solid var(--border-subtle)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontSize: "0.75rem",
                    color: "var(--text-muted)",
                    backgroundColor: "rgba(0, 0, 0, 0.2)",
                  }}
                >
                  <span>
                    Pg {issuesData.page}/{issuesData.total_pages}
                  </span>
                  <div style={{ display: "flex", gap: "0.35rem" }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      style={{ padding: "2px 6px", fontSize: "0.7rem" }}
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      <ChevronLeft size={13} />
                    </button>
                    <button
                      className="btn btn-secondary btn-sm"
                      style={{ padding: "2px 6px", fontSize: "0.7rem" }}
                      disabled={page >= issuesData.total_pages}
                      onClick={() => setPage((p) => Math.min(issuesData.total_pages, p + 1))}
                    >
                      <ChevronRight size={13} />
                    </button>
                  </div>
                </div>
              </div>

              {/* CENTER PANEL: MAIN TECHNICAL ANALYSIS & CONTEXT */}
              <div className="workspace-panel-center">
                <div className="workspace-panel-header">
                  <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--text-primary)" }}>
                    Technical Details & Context
                  </span>

                  {selectedIssueItem && (
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <button
                        className="btn btn-ghost btn-sm"
                        style={{ padding: "2px 6px", fontSize: "0.75rem", color: "var(--text-secondary)" }}
                        onClick={() => onSelectIssue(selectedIssueItem)}
                        title="Open Fullscreen Focus Modal"
                      >
                        <Maximize2 size={13} />
                        <span>Fullscreen</span>
                      </button>

                      <a
                        href={selectedIssueItem.html_url}
                        target="_blank"
                        rel="noreferrer"
                        className="btn btn-ghost btn-sm"
                        style={{ padding: "2px 6px", fontSize: "0.75rem", color: "var(--text-secondary)" }}
                        title="View on GitHub"
                      >
                        <ExternalLink size={13} />
                      </a>
                    </div>
                  )}
                </div>

                <div className="workspace-panel-content">
                  {!selectedIssueItem ? (
                    <div style={{ textAlign: "center", padding: "4rem 1.5rem", color: "var(--text-muted)" }}>
                      <CircleDot size={36} style={{ margin: "0 auto 0.75rem auto", opacity: 0.5 }} />
                      <h4 style={{ fontSize: "1rem", color: "var(--text-secondary)", marginBottom: "0.35rem" }}>
                        Select an issue from the explorer
                      </h4>
                      <p style={{ fontSize: "0.825rem", maxWidth: "340px", margin: "0 auto" }}>
                        Click any issue in the left panel to inspect its technical body, root-cause diagnosis, and AI solution.
                      </p>
                    </div>
                  ) : (
                    <div>
                      {/* Issue Header Info */}
                      <div style={{ marginBottom: "1rem" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.4rem", flexWrap: "wrap" }}>
                          <span
                            className={`badge ${
                              selectedIssueItem.state.toLowerCase() === "open"
                                ? "badge-open"
                                : "badge-closed"
                            }`}
                          >
                            {selectedIssueItem.state.toUpperCase()}
                          </span>
                          <span style={{ fontFamily: "var(--font-mono)", fontSize: "0.825rem", color: "var(--text-muted)" }}>
                            #{selectedIssueItem.issue_number}
                          </span>
                          <span style={{ fontSize: "0.775rem", color: "var(--text-muted)" }}>
                            opened by <strong>{selectedIssueItem.author || "Unknown"}</strong> on {new Date(selectedIssueItem.created_at).toLocaleDateString()}
                          </span>
                        </div>

                        <h2 style={{ fontSize: "1.15rem", fontWeight: 700, color: "var(--text-primary)", lineHeight: 1.4 }}>
                          {selectedIssueItem.title}
                        </h2>

                        {/* Labels */}
                        {selectedIssueItem.labels && selectedIssueItem.labels.length > 0 && (
                          <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
                            {selectedIssueItem.labels.map((lbl, idx) => {
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
                        )}
                      </div>

                      {/* AI Root Cause Hypothesis (if diagnosed) */}
                      {inlineAnalysis?.root_cause_hypothesis && (
                        <div
                          className="card"
                          style={{
                            padding: "0.85rem 1rem",
                            backgroundColor: "rgba(99, 102, 241, 0.08)",
                            border: "1px solid rgba(99, 102, 241, 0.25)",
                            marginBottom: "1rem",
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.35rem" }}>
                            <Lightbulb size={15} color="#818cf8" />
                            <strong style={{ fontSize: "0.825rem", color: "#a5b4fc" }}>
                              Root Cause Hypothesis
                            </strong>
                          </div>
                          <p style={{ fontSize: "0.825rem", color: "var(--text-primary)", lineHeight: 1.5 }}>
                            {inlineAnalysis.root_cause_hypothesis}
                          </p>
                        </div>
                      )}

                      {/* Extracted Stack Trace (if present) */}
                      {inlineAnalysis?.extracted_stack_trace && (
                        <div style={{ marginBottom: "1rem" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.35rem" }}>
                            <Terminal size={13} color="#f59e0b" />
                            <span style={{ fontSize: "0.725rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                              Detected Stack Trace
                            </span>
                          </div>
                          <div className="code-container" style={{ padding: "0.6rem 0.85rem", maxHeight: "180px" }}>
                            <pre style={{ margin: 0, color: "#fca5a5", fontSize: "0.775rem" }}>
                              {inlineAnalysis.extracted_stack_trace}
                            </pre>
                          </div>
                        </div>
                      )}

                      {/* Issue Description Body */}
                      <div>
                        <div style={{ fontSize: "0.725rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "0.4rem" }}>
                          Issue Description
                        </div>
                        <div
                          style={{
                            backgroundColor: "rgba(255, 255, 255, 0.02)",
                            border: "1px solid var(--border-subtle)",
                            borderRadius: "var(--radius-sm)",
                            padding: "0.85rem 1rem",
                            fontSize: "0.825rem",
                            color: "var(--text-primary)",
                            whiteSpace: "pre-wrap",
                            wordBreak: "break-word",
                            lineHeight: 1.6,
                            maxHeight: "300px",
                            overflowY: "auto",
                          }}
                        >
                          {selectedIssueItem.body || "No description provided."}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* RIGHT PANEL: AI INSIGHTS & PROPOSED CODE FIX */}
              <div className="workspace-panel-right">
                <div className="workspace-panel-header">
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <Cpu size={15} color="#818cf8" />
                    <span style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--text-primary)" }}>
                      AI Insights & Solution
                    </span>
                  </div>

                  {selectedIssueItem && (
                    <button
                      className="btn btn-secondary btn-sm"
                      style={{ padding: "2px 7px", fontSize: "0.725rem" }}
                      onClick={handleRunInlineDiagnosis}
                      disabled={diagnosingInline}
                      title="Run AI triage and generate fix patch"
                    >
                      {diagnosingInline ? (
                        <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />
                      ) : (
                        <Sparkles size={12} color="#a78bfa" />
                      )}
                      <span>{inlineAnalysis ? "Re-diagnose" : "Diagnose"}</span>
                    </button>
                  )}
                </div>

                <div className="workspace-panel-content">
                  {loadingInlineAnalysis ? (
                    <div style={{ textAlign: "center", padding: "3rem 1rem" }}>
                      <div className="spinner spinner-sm" style={{ margin: "0 auto 0.5rem auto" }} />
                      <span style={{ fontSize: "0.775rem", color: "var(--text-muted)" }}>
                        Loading AI diagnosis...
                      </span>
                    </div>
                  ) : !selectedIssueItem ? (
                    <div style={{ textAlign: "center", padding: "3rem 1rem", color: "var(--text-muted)" }}>
                      <Wrench size={32} style={{ margin: "0 auto 0.75rem auto", opacity: 0.5 }} />
                      <span style={{ fontSize: "0.8rem", display: "block" }}>
                        Select an issue to view automated code patches and recommendations.
                      </span>
                    </div>
                  ) : !inlineAnalysis ? (
                    <div className="empty-state" style={{ padding: "2rem 1rem", margin: 0 }}>
                      <Sparkles size={32} className="empty-state-icon" color="#818cf8" />
                      <h4 style={{ fontSize: "0.9rem", color: "var(--text-primary)", marginBottom: "0.25rem" }}>
                        Not Diagnosed Yet
                      </h4>
                      <p style={{ fontSize: "0.775rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
                        Run the AI diagnostic inspector to classify priority, isolate error vectors, and generate verified code patches.
                      </p>
                      <button
                        className="btn btn-primary btn-sm"
                        onClick={handleRunInlineDiagnosis}
                        disabled={diagnosingInline}
                      >
                        {diagnosingInline ? (
                          <>
                            <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} />
                            <span>Diagnosing...</span>
                          </>
                        ) : (
                          <>
                            <Sparkles size={13} />
                            <span>Run AI Diagnosis Now</span>
                          </>
                        )}
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                      {/* Priority & Classification Badges */}
                      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" }}>
                        <span
                          className="badge"
                          style={{
                            backgroundColor: "rgba(99, 102, 241, 0.15)",
                            color: "#a5b4fc",
                            border: "1px solid rgba(99, 102, 241, 0.35)",
                            fontSize: "0.725rem",
                            textTransform: "capitalize",
                          }}
                        >
                          {inlineAnalysis.category.replace("_", " ")} ({Math.round(inlineAnalysis.confidence * 100)}%)
                        </span>

                        <span
                          className="badge"
                          style={{ ...getPriorityStyle(inlineAnalysis.priority), fontSize: "0.725rem" }}
                        >
                          {inlineAnalysis.priority}
                        </span>

                        {inlineAnalysis.stack_trace_detected && (
                          <span className="badge badge-open" style={{ fontSize: "0.675rem" }}>
                            Stack Trace
                          </span>
                        )}
                      </div>

                      {/* Actionable Recommendations */}
                      {inlineAnalysis.recommendations && inlineAnalysis.recommendations.length > 0 && (
                        <div>
                          <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", display: "block", marginBottom: "0.35rem" }}>
                            Recommendations ({inlineAnalysis.recommendations.length})
                          </span>
                          <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem" }}>
                            {inlineAnalysis.recommendations.map((rec, i) => (
                              <div
                                key={i}
                                className="card"
                                style={{
                                  padding: "0.6rem 0.75rem",
                                  fontSize: "0.775rem",
                                  display: "flex",
                                  gap: "0.5rem",
                                  alignItems: "flex-start",
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
                                    marginTop: "5px",
                                    flexShrink: 0,
                                  }}
                                />
                                <div>
                                  <strong style={{ color: "var(--text-primary)" }}>{rec.action_title}</strong>
                                  <p style={{ color: "var(--text-secondary)", marginTop: "1px" }}>{rec.rationale}</p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Proposed Code Solution Patch */}
                      {inlineAnalysis.proposed_code_patch && (
                        <div>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                              <Code2 size={13} color="#818cf8" />
                              <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                                Proposed Code Patch
                              </span>
                            </div>

                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleCopy(inlineAnalysis.proposed_code_patch!, "patch")}
                              style={{ padding: "2px 6px", fontSize: "0.7rem" }}
                            >
                              {copiedPatch ? <Check size={11} color="#34d399" /> : <Copy size={11} />}
                              <span>{copiedPatch ? "Copied" : "Copy"}</span>
                            </button>
                          </div>

                          {inlineAnalysis.fix_target_file && (
                            <div style={{ fontSize: "0.725rem", color: "var(--text-muted)", marginBottom: "0.25rem", display: "flex", alignItems: "center", gap: "0.3rem" }}>
                              <FileCode size={12} color="#818cf8" />
                              <code>{inlineAnalysis.fix_target_file}</code>
                            </div>
                          )}

                          <div className="code-container" style={{ maxHeight: "200px" }}>
                            {inlineAnalysis.proposed_code_patch.split("\n").map((line, idx) =>
                              renderDiffLine(line, idx)
                            )}
                          </div>
                        </div>
                      )}

                      {/* Automated Regression Test */}
                      {inlineAnalysis.verification_test_code && (
                        <div>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.35rem" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                              <CheckCircle2 size={13} color="#34d399" />
                              <span style={{ fontSize: "0.7rem", fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase" }}>
                                Verification Test
                              </span>
                            </div>

                            <button
                              className="btn btn-secondary btn-sm"
                              onClick={() => handleCopy(inlineAnalysis.verification_test_code!, "test")}
                              style={{ padding: "2px 6px", fontSize: "0.7rem" }}
                            >
                              {copiedTest ? <Check size={11} color="#34d399" /> : <Copy size={11} />}
                              <span>{copiedTest ? "Copied" : "Copy"}</span>
                            </button>
                          </div>

                          <div className="code-container" style={{ padding: "0.5rem 0.75rem", maxHeight: "160px" }}>
                            <pre style={{ margin: 0, color: "#93c5fd", fontSize: "0.75rem" }}>
                              {inlineAnalysis.verification_test_code}
                            </pre>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            /* ====================================================================
               MODE 2: FULL DATA TABLE VIEW
               ==================================================================== */
            <>
              {/* Filter and Search Bar */}
              <div
                className="card"
                style={{
                  marginBottom: "1.25rem",
                  padding: "0.875rem 1.25rem",
                  display: "flex",
                  flexWrap: "wrap",
                  alignItems: "center",
                  gap: "1rem",
                  justifyContent: "space-between",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap", flex: 1 }}>
                  {/* Title Search */}
                  <div style={{ position: "relative", minWidth: "220px", flex: 1, maxWidth: "340px" }}>
                    <input
                      type="text"
                      className="form-input"
                      style={{ paddingLeft: "2.25rem", paddingRight: titleSearch ? "2rem" : "0.75rem" }}
                      placeholder="Filter issues by title keywords..."
                      value={titleSearch}
                      onChange={(e) => {
                        setTitleSearch(e.target.value);
                        setPage(1);
                      }}
                    />
                    <Search
                      size={14}
                      style={{
                        position: "absolute",
                        left: "0.85rem",
                        top: "50%",
                        transform: "translateY(-50%)",
                        color: "var(--text-muted)",
                      }}
                    />
                    {titleSearch && (
                      <button
                        onClick={() => setTitleSearch("")}
                        style={{
                          position: "absolute",
                          right: "0.5rem",
                          top: "50%",
                          transform: "translateY(-50%)",
                          background: "none",
                          border: "none",
                          color: "var(--text-muted)",
                          cursor: "pointer",
                        }}
                      >
                        <X size={14} />
                      </button>
                    )}
                  </div>

                  {/* Status Filter */}
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <Filter size={14} color="var(--text-muted)" />
                    <select
                      className="form-select"
                      style={{ width: "auto", minWidth: "130px" }}
                      value={statusFilter}
                      onChange={(e) => {
                        setStatusFilter(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="all">All States</option>
                      <option value="open">Open Only</option>
                      <option value="closed">Closed Only</option>
                    </select>
                  </div>

                  {/* Label Filter */}
                  <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                    <Tag size={14} color="var(--text-muted)" />
                    <select
                      className="form-select"
                      style={{ width: "auto", maxWidth: "200px" }}
                      value={selectedLabel}
                      onChange={(e) => {
                        setSelectedLabel(e.target.value);
                        setPage(1);
                      }}
                    >
                      <option value="all">All Labels ({labels.length})</option>
                      {labels.map((l) => (
                        <option key={l} value={l}>
                          {l}
                        </option>
                      ))}
                    </select>
                  </div>

                  {hasActiveFilters && (
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={handleResetFilters}
                      style={{ fontSize: "0.75rem", padding: "0.3rem 0.6rem" }}
                    >
                      Clear Filters
                    </button>
                  )}
                </div>

                {/* Page size selector */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Per page:</span>
                  <select
                    className="form-select"
                    style={{ width: "auto" }}
                    value={perPage}
                    onChange={(e) => {
                      setPerPage(Number(e.target.value));
                      setPage(1);
                    }}
                  >
                    <option value={10}>10</option>
                    <option value={20}>20</option>
                    <option value={50}>50</option>
                  </select>
                </div>
              </div>

              {/* Loading Skeletons */}
              {loading && (
                <div className="card" style={{ padding: "1.5rem" }}>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <div
                      key={n}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "1rem",
                        padding: "0.85rem 0",
                        borderBottom: n < 5 ? "1px solid var(--border-subtle)" : "none",
                      }}
                    >
                      <div className="skeleton" style={{ width: "40px", height: "16px" }} />
                      <div style={{ flex: 1 }}>
                        <div className="skeleton" style={{ width: "65%", height: "16px", marginBottom: "6px" }} />
                        <div className="skeleton" style={{ width: "35%", height: "12px" }} />
                      </div>
                      <div className="skeleton" style={{ width: "70px", height: "22px" }} />
                      <div className="skeleton" style={{ width: "90px", height: "14px" }} />
                    </div>
                  ))}
                </div>
              )}

              {/* Empty State */}
              {!loading && issuesData.items.length === 0 && (
                <div className="empty-state">
                  <Filter size={40} className="empty-state-icon" />
                  <h3 className="empty-state-title">No Issues Found</h3>
                  <p className="empty-state-desc">
                    {hasActiveFilters
                      ? "No issues match your current query or label filters. Try resetting the filters."
                      : "This repository has no stored issues yet. Trigger a sync to pull issues from GitHub."}
                  </p>
                  {hasActiveFilters && (
                    <button className="btn btn-primary btn-sm" onClick={handleResetFilters}>
                      Reset All Filters
                    </button>
                  )}
                </div>
              )}

              {/* Issues Data Table */}
              {!loading && issuesData.items.length > 0 && (
                <div className="data-table-wrapper">
                  <div style={{ overflowX: "auto" }}>
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th style={{ width: "80px" }}>#</th>
                          <th>Title & Labels</th>
                          <th style={{ width: "110px" }}>Status</th>
                          <th style={{ width: "140px" }}>Author</th>
                          <th style={{ width: "100px", textAlign: "center" }}>Comments</th>
                          <th style={{ width: "120px", textAlign: "right" }}>Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {issuesData.items.map((issue) => (
                          <tr
                            key={issue.id}
                            className="data-table-row"
                            onClick={() => onSelectIssue(issue)}
                          >
                            <td
                              style={{
                                color: "var(--text-muted)",
                                fontFamily: "var(--font-mono)",
                                fontSize: "0.8125rem",
                              }}
                            >
                              #{issue.issue_number}
                            </td>

                            <td>
                              <div
                                style={{
                                  fontWeight: 600,
                                  color: "var(--text-primary)",
                                  marginBottom: "0.35rem",
                                  lineHeight: 1.4,
                                }}
                              >
                                {issue.title}
                              </div>

                              {/* Labels Chips */}
                              {issue.labels && issue.labels.length > 0 && (
                                <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
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
                              )}
                            </td>

                            <td>
                              <span
                                className={`badge ${
                                  issue.state.toLowerCase() === "open" ? "badge-open" : "badge-closed"
                                }`}
                              >
                                {issue.state.toUpperCase()}
                              </span>
                            </td>

                            <td style={{ color: "var(--text-secondary)", fontSize: "0.8125rem" }}>
                              {issue.author || "Unknown"}
                            </td>

                            <td style={{ textAlign: "center", color: "var(--text-muted)", fontSize: "0.8125rem" }}>
                              <span style={{ display: "inline-flex", alignItems: "center", gap: "0.25rem" }}>
                                <MessageSquare size={13} />
                                {issue.comments_count}
                              </span>
                            </td>

                            <td
                              style={{
                                textAlign: "right",
                                color: "var(--text-muted)",
                                fontSize: "0.775rem",
                              }}
                            >
                              {new Date(issue.created_at).toLocaleDateString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination Controls Footer */}
                  <div
                    style={{
                      padding: "0.85rem 1.25rem",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      borderTop: "1px solid var(--border-subtle)",
                      backgroundColor: "rgba(255, 255, 255, 0.015)",
                      flexWrap: "wrap",
                      gap: "1rem",
                    }}
                  >
                    <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                      Showing {issuesData.items.length > 0 ? (page - 1) * perPage + 1 : 0} to{" "}
                      {Math.min(page * perPage, issuesData.total)} of {issuesData.total} issues
                    </span>

                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                      <span style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginRight: "0.5rem" }}>
                        Page {issuesData.page} of {issuesData.total_pages}
                      </span>

                      <button
                        className="btn btn-secondary btn-sm"
                        disabled={page <= 1}
                        onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                      >
                        <ChevronLeft size={15} />
                        <span>Prev</span>
                      </button>

                      <button
                        className="btn btn-secondary btn-sm"
                        disabled={page >= issuesData.total_pages}
                        onClick={() => setPage((prev) => Math.min(issuesData.total_pages, prev + 1))}
                      >
                        <span>Next</span>
                        <ChevronRight size={15} />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
};
