import React, { useEffect, useState } from "react";
import { apiGetRepositoryPullRequests } from "../api";
import { Issue, PaginatedPullRequests, PullRequest, Repository } from "../types";
import { PullRequestDetailModal } from "./PullRequestDetailModal";
import {
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Columns,
  ExternalLink,
  Filter,
  GitMerge,
  GitPullRequest,
  RefreshCw,
  Search,
  X,
} from "lucide-react";

interface PullRequestExplorerProps {
  repository: Repository;
  onSyncRepo?: () => void;
  onSelectIssue?: (issue: Issue) => void;
}

export const PullRequestExplorer: React.FC<PullRequestExplorerProps> = ({
  repository,
  onSyncRepo,
  onSelectIssue,
}) => {
  const [prsData, setPrsData] = useState<PaginatedPullRequests>({
    items: [],
    total: 0,
    page: 1,
    per_page: 10,
    total_pages: 1,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPr, setSelectedPr] = useState<PullRequest | null>(null);

  // Filters state
  const [page, setPage] = useState(1);
  const [perPage, setPerPage] = useState(10);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [titleSearch, setTitleSearch] = useState<string>("");

  useEffect(() => {
    let isCancelled = false;

    async function loadPullRequests() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiGetRepositoryPullRequests(repository.id, {
          page,
          per_page: perPage,
          status: statusFilter,
          title: titleSearch,
        });
        if (!isCancelled) {
          setPrsData(data);
        }
      } catch (err: any) {
        if (!isCancelled) {
          setError(err.message || "Failed to load pull requests.");
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    }

    loadPullRequests();
    return () => {
      isCancelled = true;
    };
  }, [repository.id, page, perPage, statusFilter, titleSearch]);

  const handleResetFilters = () => {
    setStatusFilter("all");
    setTitleSearch("");
    setPage(1);
  };

  const hasActiveFilters = statusFilter !== "all" || titleSearch.trim() !== "";

  return (
    <div>
      {/* Search and Filters Bar */}
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
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "0.75rem",
            flexWrap: "wrap",
            flex: 1,
          }}
        >
          {/* Title Search */}
          <div
            style={{
              position: "relative",
              minWidth: "220px",
              flex: 1,
              maxWidth: "340px",
            }}
          >
            <input
              type="text"
              className="form-input"
              style={{
                paddingLeft: "2.25rem",
                paddingRight: titleSearch ? "2rem" : "0.75rem",
              }}
              placeholder="Search pull requests..."
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
              style={{ width: "auto", minWidth: "150px" }}
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="all">All Pull Requests</option>
              <option value="open">Open Only</option>
              <option value="merged">Merged Only</option>
              <option value="closed">Closed (Unmerged) Only</option>
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

        {/* Page size selector & Sync trigger */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          {onSyncRepo && (
            <button
              className="btn btn-secondary btn-sm"
              onClick={onSyncRepo}
              title="Sync repository with GitHub to ingest latest PRs"
            >
              <RefreshCw size={13} />
              <span>Sync PRs</span>
            </button>
          )}

          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
              Per page:
            </span>
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
      </div>

      {/* Error alert */}
      {error && (
        <div className="alert alert-danger">
          <AlertCircle size={16} style={{ flexShrink: 0, marginTop: "2px" }} />
          <div>{error}</div>
        </div>
      )}

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
                <div className="skeleton" style={{ width: "60%", height: "16px", marginBottom: "6px" }} />
                <div className="skeleton" style={{ width: "30%", height: "12px" }} />
              </div>
              <div className="skeleton" style={{ width: "80px", height: "22px" }} />
              <div className="skeleton" style={{ width: "100px", height: "26px" }} />
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && prsData.items.length === 0 && (
        <div className="empty-state">
          <GitPullRequest size={40} className="empty-state-icon" />
          <h3 className="empty-state-title">No Pull Requests Found</h3>
          <p className="empty-state-desc">
            {hasActiveFilters
              ? "No pull requests match your search criteria. Try adjusting or clearing filters."
              : "No pull requests have been stored for this repository yet. Trigger a sync to ingest PRs."}
          </p>

          <div style={{ display: "flex", justifyContent: "center", gap: "0.75rem" }}>
            {hasActiveFilters && (
              <button className="btn btn-secondary btn-sm" onClick={handleResetFilters}>
                Reset Filters
              </button>
            )}
            {onSyncRepo && !hasActiveFilters && (
              <button className="btn btn-primary btn-sm" onClick={onSyncRepo}>
                <RefreshCw size={14} />
                <span>Sync Repository from GitHub</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* PR Table / List */}
      {!loading && prsData.items.length > 0 && (
        <div className="data-table-wrapper">
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: "80px" }}>#</th>
                  <th>Title & Labels</th>
                  <th style={{ width: "120px" }}>Status</th>
                  <th style={{ width: "140px" }}>Author</th>
                  <th style={{ width: "130px", textAlign: "right" }}>Date</th>
                  <th style={{ width: "160px", textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {prsData.items.map((pr) => {
                  const isMerged = pr.is_merged || pr.state.toLowerCase() === "merged";
                  const isOpen = pr.state.toLowerCase() === "open";

                  return (
                    <tr
                      key={pr.id}
                      className="data-table-row"
                      onClick={() => setSelectedPr(pr)}
                    >
                      <td
                        style={{
                          color: "var(--text-muted)",
                          fontFamily: "var(--font-mono)",
                          fontSize: "0.8125rem",
                        }}
                      >
                        #{pr.pr_number}
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
                          {pr.title}
                        </div>

                        {/* Labels */}
                        {pr.labels && pr.labels.length > 0 && (
                          <div style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                            {pr.labels.map((lbl, idx) => {
                              const name = typeof lbl === "string" ? lbl : lbl.name;
                              const color =
                                typeof lbl === "string" ? "4b5563" : lbl.color || "4b5563";
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
                        {isMerged ? (
                          <span className="badge badge-merged">
                            <GitMerge size={12} />
                            <span>MERGED</span>
                          </span>
                        ) : isOpen ? (
                          <span className="badge badge-open">
                            <GitPullRequest size={12} />
                            <span>OPEN</span>
                          </span>
                        ) : (
                          <span className="badge badge-closed">
                            <GitPullRequest size={12} />
                            <span>CLOSED</span>
                          </span>
                        )}
                      </td>

                      <td style={{ color: "var(--text-secondary)", fontSize: "0.8125rem" }}>
                        {pr.author || "Unknown"}
                      </td>

                      <td
                        style={{
                          textAlign: "right",
                          color: "var(--text-muted)",
                          fontSize: "0.775rem",
                        }}
                      >
                        {isMerged && pr.merged_at
                          ? `Merged ${new Date(pr.merged_at).toLocaleDateString()}`
                          : new Date(pr.created_at).toLocaleDateString()}
                      </td>

                      <td
                        style={{ textAlign: "right" }}
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "0.4rem",
                          }}
                        >
                          <button
                            className="btn btn-secondary btn-sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedPr(pr);
                            }}
                            style={{
                              padding: "0.275rem 0.65rem",
                              fontSize: "0.75rem",
                              color: "#a5b4fc",
                              borderColor: "rgba(99, 102, 241, 0.35)",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: "0.35rem",
                            }}
                            title="Inspect Split Diff & Changes"
                          >
                            <Columns size={12} />
                            <span>Split Diff</span>
                          </button>

                          {pr.html_url && (
                            <a
                              href={pr.html_url}
                              target="_blank"
                              rel="noreferrer"
                              className="btn btn-ghost btn-sm"
                              style={{ padding: "0.275rem 0.45rem" }}
                              title="Open on GitHub"
                            >
                              <ExternalLink size={13} />
                            </a>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
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
              Showing {prsData.items.length > 0 ? (page - 1) * perPage + 1 : 0} to{" "}
              {Math.min(page * perPage, prsData.total)} of {prsData.total} pull requests
            </span>

            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span
                style={{
                  fontSize: "0.8125rem",
                  color: "var(--text-secondary)",
                  marginRight: "0.5rem",
                }}
              >
                Page {prsData.page} of {prsData.total_pages}
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
                disabled={page >= prsData.total_pages}
                onClick={() => setPage((prev) => Math.min(prsData.total_pages, prev + 1))}
              >
                <span>Next</span>
                <ChevronRight size={15} />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* PR Detail Modal */}
      <PullRequestDetailModal
        pr={selectedPr}
        onClose={() => setSelectedPr(null)}
        onSelectIssue={onSelectIssue}
      />
    </div>
  );
};
