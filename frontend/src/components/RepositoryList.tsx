import React, { useEffect, useState } from "react";
import { apiGetRepoIndexStatus, apiIndexRepoCode } from "../api";
import { CodeIndexStatus, Repository } from "../types";
import {
  ArrowRight,
  CheckCircle2,
  Clock,
  ExternalLink,
  FileCode,
  FolderGit2,
  GitFork,
  Plus,
  RefreshCw,
  Search,
  Shield,
  Sparkles,
  Star,
  Trash2,
  X,
} from "lucide-react";

interface RepositoryListProps {
  repositories: Repository[];
  loading: boolean;
  onSelectRepo: (repo: Repository) => void;
  onDeleteRepo: (repo: Repository) => void;
  onSyncRepo: (repo: Repository) => void;
  onOpenAddRepo: () => void;
  onQuickIngest?: (repoUrlOrName: string) => void;
}

const getLanguageColor = (lang: string | null): string => {
  if (!lang) return "#94a3b8";
  switch (lang.toLowerCase()) {
    case "python":
      return "#3572A5";
    case "typescript":
      return "#3178c6";
    case "javascript":
      return "#f1e05a";
    case "rust":
      return "#dea584";
    case "go":
      return "#00ADD8";
    case "java":
      return "#b07219";
    case "c++":
    case "cpp":
      return "#f34b7d";
    case "c#":
    case "csharp":
      return "#178600";
    case "ruby":
      return "#701516";
    default:
      return "#6366f1";
  }
};

export const RepositoryList: React.FC<RepositoryListProps> = ({
  repositories,
  loading,
  onSelectRepo,
  onDeleteRepo,
  onSyncRepo,
  onOpenAddRepo,
  onQuickIngest,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [indexingIds, setIndexingIds] = useState<Set<number>>(new Set());
  const [indexStatuses, setIndexStatuses] = useState<Record<number, CodeIndexStatus>>({});
  const [onboardingInput, setOnboardingInput] = useState("");
  const [inputError, setInputError] = useState<string | null>(null);

  // Poll or load code indexing status for all loaded repositories
  useEffect(() => {
    if (repositories.length === 0) return;
    repositories.forEach(async (repo) => {
      try {
        const st = await apiGetRepoIndexStatus(repo.id);
        setIndexStatuses((prev) => ({ ...prev, [repo.id]: st }));
      } catch {
        // Not yet indexed
      }
    });
  }, [repositories]);

  const handleIndexCode = async (repo: Repository, e: React.MouseEvent) => {
    e.stopPropagation();
    setIndexingIds((prev) => new Set(prev).add(repo.id));
    try {
      const res = await apiIndexRepoCode(repo.id);
      setIndexStatuses((prev) => ({
        ...prev,
        [repo.id]: {
          repository_id: repo.id,
          status: res.status,
          total_files: res.total_files_discovered,
          indexed_chunks: res.total_chunks_indexed,
          last_indexed_at: new Date().toISOString(),
          error_message: null,
        },
      }));
    } catch (err: any) {
      console.warn("Failed to index repository source code:", err);
    } finally {
      setIndexingIds((prev) => {
        const next = new Set(prev);
        next.delete(repo.id);
        return next;
      });
    }
  };

  const isFirstTimeUser = !loading && repositories.length === 0;

  const filteredRepos = repositories.filter(
    (r) =>
      r.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.description && r.description.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (r.language && r.language.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const handleSync = async (repo: Repository, e: React.MouseEvent) => {
    e.stopPropagation();
    setSyncingId(repo.id);
    try {
      await onSyncRepo(repo);
    } finally {
      setSyncingId(null);
    }
  };

  const handleDelete = (repo: Repository, e: React.MouseEvent) => {
    e.stopPropagation();
    if (
      window.confirm(
        `Are you sure you want to remove "${repo.full_name}" from RepoMind? All stored issues and PR diffs will be deleted.`
      )
    ) {
      onDeleteRepo(repo);
    }
  };

  const handleOnboardingSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setInputError(null);
    const trimmed = onboardingInput.trim();
    if (!trimmed) {
      setInputError("Please enter a GitHub repository name (e.g. pallets/flask) or URL.");
      return;
    }

    if (onQuickIngest) {
      onQuickIngest(trimmed);
    } else {
      onOpenAddRepo();
    }
    setOnboardingInput("");
  };

  const handleSelectExample = (example: string) => {
    if (onQuickIngest) {
      onQuickIngest(example);
    } else {
      onOpenAddRepo();
    }
  };

  // Real calculated totals from actual loaded repositories
  const totalIssuesTracked = repositories.reduce(
    (acc, r) => acc + (r.stored_issues_count ?? r.open_issues_count ?? 0),
    0
  );

  const totalStarsIndexed = repositories.reduce(
    (acc, r) => acc + (r.stargazers_count ?? 0),
    0
  );

  return (
    <div>
      {/* ====================================================================
          1. FIRST-TIME USER EXPERIENCE: INTENTIONAL ONBOARDING WORKSPACE
          ==================================================================== */}
      {isFirstTimeUser && (
        <div style={{ maxWidth: "860px", margin: "1rem auto 2.5rem auto" }}>
          {/* Welcome Header */}
          <div style={{ textAlign: "center", marginBottom: "2rem" }}>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "4px 10px",
                borderRadius: "var(--radius-full)",
                backgroundColor: "rgba(99, 102, 241, 0.12)",
                border: "1px solid rgba(99, 102, 241, 0.3)",
                color: "#a5b4fc",
                fontSize: "0.775rem",
                fontWeight: 600,
                marginBottom: "1rem",
              }}
            >
              <Sparkles size={13} />
              <span>AI-Powered GitHub Intelligence</span>
            </div>

            <h1 style={{ fontSize: "2.1rem", fontWeight: 800, letterSpacing: "-0.03em", lineHeight: 1.25, color: "#ffffff" }}>
              Connect your first GitHub repository
            </h1>

            <p style={{ color: "var(--text-secondary)", fontSize: "0.95rem", marginTop: "0.6rem", maxWidth: "620px", margin: "0.6rem auto 0 auto", lineHeight: 1.6 }}>
              RepoMind synchronizes open-source issues, isolates stack traces, generates automated root-cause hypotheses, and inspects pull request code diffs.
            </p>
          </div>

          {/* Primary Ingestion Form Card */}
          <div
            className="card"
            style={{
              padding: "2rem",
              backgroundColor: "var(--bg-card)",
              border: "1px solid var(--border-color)",
              boxShadow: "var(--shadow-lg), 0 0 32px -4px rgba(99, 102, 241, 0.15)",
              borderRadius: "var(--radius-lg)",
              marginBottom: "2rem",
            }}
          >
            <form onSubmit={handleOnboardingSubmit}>
              <label
                style={{
                  display: "block",
                  fontSize: "0.85rem",
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  marginBottom: "0.6rem",
                }}
              >
                GitHub Repository URL or Identifier
              </label>

              <div
                style={{
                  display: "flex",
                  gap: "0.5rem",
                  alignItems: "center",
                  flexWrap: "wrap",
                }}
              >
                <div style={{ position: "relative", flex: 1, minWidth: "260px" }}>
                  <input
                    type="text"
                    className="form-input"
                    style={{
                      paddingLeft: "2.5rem",
                      paddingRight: "1rem",
                      height: "44px",
                      fontSize: "0.925rem",
                    }}
                    placeholder="e.g. pallets/flask or https://github.com/pallets/flask"
                    value={onboardingInput}
                    onChange={(e) => {
                      setOnboardingInput(e.target.value);
                      setInputError(null);
                    }}
                  />
                  <FolderGit2
                    size={16}
                    style={{
                      position: "absolute",
                      left: "0.95rem",
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "var(--text-muted)",
                    }}
                  />
                </div>

                <button
                  type="submit"
                  className="btn btn-primary"
                  style={{
                    height: "44px",
                    padding: "0 1.25rem",
                    fontSize: "0.9rem",
                    fontWeight: 600,
                  }}
                >
                  <span>Connect & Analyze</span>
                  <ArrowRight size={15} />
                </button>
              </div>

              {inputError && (
                <p style={{ color: "#f87171", fontSize: "0.8rem", marginTop: "0.5rem" }}>
                  {inputError}
                </p>
              )}

              {/* Verified Real Example Chips */}
              <div style={{ marginTop: "1.25rem", display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.775rem", color: "var(--text-muted)" }}>
                  Try real example projects:
                </span>
                {[
                  { name: "pallets/flask", desc: "Python Web Framework" },
                  { name: "psf/requests", desc: "HTTP Library" },
                  { name: "tiangolo/fastapi", desc: "API Framework" },
                ].map((ex) => (
                  <button
                    key={ex.name}
                    type="button"
                    onClick={() => handleSelectExample(ex.name)}
                    style={{
                      fontSize: "0.75rem",
                      padding: "3px 9px",
                      borderRadius: "var(--radius-full)",
                      backgroundColor: "rgba(255, 255, 255, 0.04)",
                      border: "1px solid var(--border-color)",
                      color: "var(--text-secondary)",
                      cursor: "pointer",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "0.35rem",
                      transition: "all var(--transition-fast)",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = "#a5b4fc";
                      e.currentTarget.style.borderColor = "var(--accent-primary)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = "var(--text-secondary)";
                      e.currentTarget.style.borderColor = "var(--border-color)";
                    }}
                    title={`Click to analyze ${ex.name} (${ex.desc})`}
                  >
                    <FolderGit2 size={12} color="#818cf8" />
                    <span>{ex.name}</span>
                  </button>
                ))}
              </div>
            </form>
          </div>

          {/* 3-Step Workflow Preview */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              gap: "1.25rem",
            }}
          >
            <div className="card" style={{ padding: "1.25rem" }}>
              <div
                style={{
                  width: "30px",
                  height: "30px",
                  borderRadius: "var(--radius-sm)",
                  backgroundColor: "rgba(99, 102, 241, 0.15)",
                  color: "#818cf8",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 700,
                  fontSize: "0.85rem",
                  marginBottom: "0.75rem",
                }}
              >
                1
              </div>
              <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)" }}>
                Connect Repository
              </h4>
              <p style={{ fontSize: "0.825rem", color: "var(--text-secondary)", marginTop: "0.35rem", lineHeight: 1.5 }}>
                Provide any public repository. Normalized into owner/repo coordinates with duplicate-safe validation.
              </p>
            </div>

            <div className="card" style={{ padding: "1.25rem" }}>
              <div
                style={{
                  width: "30px",
                  height: "30px",
                  borderRadius: "var(--radius-sm)",
                  backgroundColor: "rgba(6, 182, 212, 0.15)",
                  color: "#06b6d4",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 700,
                  fontSize: "0.85rem",
                  marginBottom: "0.75rem",
                }}
              >
                2
              </div>
              <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)" }}>
                Ingest Issues & PRs
              </h4>
              <p style={{ fontSize: "0.825rem", color: "var(--text-secondary)", marginTop: "0.35rem", lineHeight: 1.5 }}>
                Asynchronous background worker retrieves issues, comments, labels, and pull request changesets via GitHub REST API.
              </p>
            </div>

            <div className="card" style={{ padding: "1.25rem" }}>
              <div
                style={{
                  width: "30px",
                  height: "30px",
                  borderRadius: "var(--radius-sm)",
                  backgroundColor: "rgba(16, 185, 129, 0.15)",
                  color: "#10b981",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: 700,
                  fontSize: "0.85rem",
                  marginBottom: "0.75rem",
                }}
              >
                3
              </div>
              <h4 style={{ fontSize: "0.95rem", fontWeight: 700, color: "var(--text-primary)" }}>
                AI Triage & Diffs
              </h4>
              <p style={{ fontSize: "0.825rem", color: "var(--text-secondary)", marginTop: "0.35rem", lineHeight: 1.5 }}>
                Diagnose root causes, isolate stack traces, generate regression tests, and review side-by-side diffs.
              </p>
            </div>
          </div>

          {/* Authentication & Privacy Note */}
          <div
            style={{
              marginTop: "1.5rem",
              padding: "0.75rem 1rem",
              borderRadius: "var(--radius-sm)",
              backgroundColor: "rgba(255, 255, 255, 0.02)",
              border: "1px solid var(--border-subtle)",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              fontSize: "0.775rem",
              color: "var(--text-muted)",
            }}
          >
            <Shield size={14} color="#10b981" style={{ flexShrink: 0 }} />
            <span>
              Public repositories do not require GitHub authentication. User credentials & ingested jobs are isolated in PostgreSQL.
            </span>
          </div>
        </div>
      )}

      {/* ====================================================================
          2. RETURNING USER EXPERIENCE: COMPACT DEVELOPER WORKSPACE
          ==================================================================== */}
      {!isFirstTimeUser && (
        <div>
          {/* Compact Action Bar & Telemetry Strip */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "1rem",
              marginBottom: "1.25rem",
              paddingBottom: "1.25rem",
              borderBottom: "1px solid var(--border-subtle)",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                <h1 style={{ fontSize: "1.45rem", fontWeight: 800, color: "var(--text-primary)", letterSpacing: "-0.02em" }}>
                  Repositories
                </h1>
                <span
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    fontFamily: "var(--font-mono)",
                    backgroundColor: "rgba(99, 102, 241, 0.15)",
                    color: "#a5b4fc",
                    padding: "2px 8px",
                    borderRadius: "var(--radius-full)",
                    border: "1px solid rgba(99, 102, 241, 0.3)",
                  }}
                >
                  {repositories.length}
                </span>
              </div>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.825rem", marginTop: "0.15rem" }}>
                Select a project to enter the 3-panel issue triage and PR diff workspace
              </p>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", flexWrap: "wrap" }}>
              {/* Search Filter */}
              <div style={{ position: "relative", minWidth: "240px" }}>
                <input
                  type="text"
                  className="form-input"
                  style={{
                    paddingLeft: "2.25rem",
                    paddingRight: searchTerm ? "2rem" : "0.75rem",
                  }}
                  placeholder="Filter repositories..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
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
                {searchTerm && (
                  <button
                    onClick={() => setSearchTerm("")}
                    style={{
                      position: "absolute",
                      right: "0.6rem",
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

              <button className="btn btn-primary btn-sm" onClick={onOpenAddRepo}>
                <Plus size={15} />
                <span>Add Repository</span>
              </button>
            </div>
          </div>

          {/* Real Metrics Strip (100% Real Data) */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "1.5rem",
              marginBottom: "1.5rem",
              padding: "0.65rem 1rem",
              backgroundColor: "rgba(255, 255, 255, 0.02)",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-subtle)",
              flexWrap: "wrap",
              fontSize: "0.8rem",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <span style={{ color: "var(--text-muted)" }}>Repositories:</span>
              <strong style={{ color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>
                {repositories.length}
              </strong>
            </div>

            <div style={{ width: "1px", height: "14px", backgroundColor: "var(--border-subtle)" }} />

            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <span style={{ color: "var(--text-muted)" }}>Total Ingested Issues:</span>
              <strong style={{ color: "#34d399", fontFamily: "var(--font-mono)" }}>
                {totalIssuesTracked.toLocaleString()}
              </strong>
            </div>

            <div style={{ width: "1px", height: "14px", backgroundColor: "var(--border-subtle)" }} />

            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
              <span style={{ color: "var(--text-muted)" }}>GitHub Stars Indexed:</span>
              <strong style={{ color: "#fbbf24", fontFamily: "var(--font-mono)" }}>
                {totalStarsIndexed.toLocaleString()}
              </strong>
            </div>

            <div style={{ width: "1px", height: "14px", backgroundColor: "var(--border-subtle)" }} />

            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginLeft: "auto" }}>
              <span className="status-dot-pulse" />
              <span style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                FastAPI Backend • Live
              </span>
            </div>
          </div>

          {/* Loading Skeletons */}
          {loading && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(350px, 1fr))",
                gap: "1.25rem",
              }}
            >
              {[1, 2, 3].map((n) => (
                <div key={n} className="card" style={{ height: "190px", padding: "1.5rem" }}>
                  <div className="skeleton" style={{ width: "60%", height: "20px", marginBottom: "1rem" }} />
                  <div className="skeleton" style={{ width: "90%", height: "14px", marginBottom: "0.5rem" }} />
                  <div className="skeleton" style={{ width: "75%", height: "14px", marginBottom: "1.5rem" }} />
                  <div style={{ display: "flex", gap: "0.75rem" }}>
                    <div className="skeleton" style={{ width: "70px", height: "20px" }} />
                    <div className="skeleton" style={{ width: "60px", height: "20px" }} />
                    <div className="skeleton" style={{ width: "80px", height: "20px" }} />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* No search results */}
          {!loading && repositories.length > 0 && filteredRepos.length === 0 && (
            <div className="empty-state">
              <Search size={36} className="empty-state-icon" />
              <h3 className="empty-state-title">No Repositories Found</h3>
              <p className="empty-state-desc">
                No synchronized repositories match the filter "<strong>{searchTerm}</strong>".
              </p>
              <button className="btn btn-secondary btn-sm" onClick={() => setSearchTerm("")}>
                Clear Filter
              </button>
            </div>
          )}

          {/* Repository Cards Grid */}
          {!loading && filteredRepos.length > 0 && (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
                gap: "1.25rem",
              }}
            >
              {filteredRepos.map((repo) => {
                const langColor = getLanguageColor(repo.language);
                const isSyncing = syncingId === repo.id;

                return (
                  <div
                    key={repo.id}
                    className="card card-hover"
                    onClick={() => onSelectRepo(repo)}
                    style={{
                      cursor: "pointer",
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      padding: "1.35rem",
                    }}
                  >
                    <div>
                      {/* Top Bar: Title & External Link */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          justifyContent: "space-between",
                          gap: "0.5rem",
                          marginBottom: "0.5rem",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", minWidth: 0 }}>
                          <div
                            style={{
                              width: "28px",
                              height: "28px",
                              borderRadius: "var(--radius-xs)",
                              backgroundColor: "rgba(255, 255, 255, 0.05)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              color: "#818cf8",
                              flexShrink: 0,
                              border: "1px solid var(--border-subtle)",
                            }}
                          >
                            <FolderGit2 size={15} />
                          </div>
                          <h3
                            style={{
                              fontSize: "1.05rem",
                              fontWeight: 700,
                              color: "var(--text-primary)",
                              letterSpacing: "-0.015em",
                              whiteSpace: "nowrap",
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                            }}
                            title={repo.full_name}
                          >
                            {repo.full_name}
                          </h3>
                        </div>

                        <a
                          href={repo.html_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          title="Open on GitHub"
                          style={{
                            color: "var(--text-muted)",
                            padding: "4px",
                            borderRadius: "4px",
                            display: "flex",
                            alignItems: "center",
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
                          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
                        >
                          <ExternalLink size={15} />
                        </a>
                      </div>

                      {/* Description */}
                      <p
                        style={{
                          color: "var(--text-secondary)",
                          fontSize: "0.825rem",
                          lineHeight: 1.5,
                          margin: "0.4rem 0 1rem 0",
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                          minHeight: "2.5rem",
                        }}
                      >
                        {repo.description || "No description provided on GitHub."}
                      </p>

                      {/* Metadata Chips */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "0.875rem",
                          flexWrap: "wrap",
                          fontSize: "0.775rem",
                          color: "var(--text-secondary)",
                        }}
                      >
                        {repo.language && (
                          <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                            <span
                              style={{
                                width: "8px",
                                height: "8px",
                                borderRadius: "50%",
                                backgroundColor: langColor,
                                display: "inline-block",
                              }}
                            />
                            <span style={{ fontWeight: 500 }}>{repo.language}</span>
                          </span>
                        )}

                        <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                          <Star size={12} color="#f59e0b" fill="#f59e0b" />
                          <span>{repo.stargazers_count.toLocaleString()}</span>
                        </span>

                        <span style={{ display: "flex", alignItems: "center", gap: "0.3rem" }}>
                          <GitFork size={12} color="var(--text-muted)" />
                          <span>{repo.forks_count.toLocaleString()}</span>
                        </span>

                        <span
                          className="badge badge-open"
                          style={{ padding: "1px 6px", fontSize: "0.7rem", fontWeight: 600 }}
                        >
                          {repo.stored_issues_count ?? repo.open_issues_count} issues
                        </span>

                        {indexStatuses[repo.id]?.status === "ready" ? (
                          <span
                            className="badge badge-success"
                            style={{
                              padding: "1px 6px",
                              fontSize: "0.7rem",
                              fontWeight: 600,
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "0.25rem",
                            }}
                            title={`Indexed ${indexStatuses[repo.id]?.indexed_chunks || 0} code chunks across ${indexStatuses[repo.id]?.total_files || 0} source files`}
                          >
                            <CheckCircle2 size={10} />
                            <span>Indexed ({indexStatuses[repo.id]?.indexed_chunks || 0})</span>
                          </span>
                        ) : indexStatuses[repo.id]?.status === "indexing" || indexingIds.has(repo.id) ? (
                          <span
                            className="badge"
                            style={{
                              padding: "1px 6px",
                              fontSize: "0.7rem",
                              fontWeight: 600,
                              backgroundColor: "rgba(99, 102, 241, 0.15)",
                              color: "#818cf8",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "0.25rem",
                            }}
                          >
                            <FileCode size={10} className="spinner" />
                            <span>Indexing...</span>
                          </span>
                        ) : null}
                      </div>
                    </div>

                    {/* Bottom Card Controls */}
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginTop: "1.25rem",
                        paddingTop: "0.85rem",
                        borderTop: "1px solid var(--border-subtle)",
                      }}
                    >
                      <span
                        style={{
                          fontSize: "0.725rem",
                          color: "var(--text-muted)",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.3rem",
                        }}
                      >
                        <Clock size={11} />
                        <span>
                          {repo.last_synced_at
                            ? `Synced ${new Date(repo.last_synced_at).toLocaleDateString()}`
                            : "Initial ingest"}
                        </span>
                      </span>

                      <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                        <button
                          className="btn btn-secondary btn-sm"
                          title="Index repository source code for semantic search"
                          disabled={indexingIds.has(repo.id) || isSyncing}
                          onClick={(e) => handleIndexCode(repo, e)}
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.3rem",
                            fontSize: "0.75rem",
                          }}
                        >
                          <FileCode
                            size={12}
                            style={{
                              color: indexStatuses[repo.id]?.status === "ready" ? "#34d399" : "#818cf8",
                            }}
                          />
                          <span>
                            {indexingIds.has(repo.id)
                              ? "Indexing..."
                              : indexStatuses[repo.id]?.status === "ready"
                              ? "Re-index"
                              : "Index Code"}
                          </span>
                        </button>

                        <button
                          className="btn btn-secondary btn-sm"
                          title="Re-synchronize latest GitHub issues & PRs"
                          disabled={isSyncing}
                          onClick={(e) => handleSync(repo, e)}
                        >
                          <RefreshCw
                            size={12}
                            style={{
                              animation: isSyncing ? "spin 1s linear infinite" : "none",
                            }}
                          />
                          <span>Sync</span>
                        </button>

                        <button
                          className="btn btn-danger btn-sm"
                          title="Remove repository"
                          onClick={(e) => handleDelete(repo, e)}
                          style={{ padding: "0.35rem 0.5rem" }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
