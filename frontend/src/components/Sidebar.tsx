import React from "react";
import { Repository, User } from "../types";
import {
  CircleDot,
  Cpu,
  FolderGit2,
  GitPullRequest,
  LogIn,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  X,
} from "lucide-react";

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  isMobileOpen: boolean;
  onCloseMobile: () => void;
  currentView: "repositories" | "issues" | "pulls";
  onNavigate: (view: "repositories" | "issues" | "pulls") => void;
  selectedRepo: Repository | null;
  onSelectRepo: (repo: Repository | null) => void;
  repositories: Repository[];
  onOpenAddRepo: () => void;
  onOpenSearch: () => void;
  user: User | null;
  onLogout: () => void;
  onOpenAuth: (mode: "login" | "register") => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onToggle,
  isMobileOpen,
  onCloseMobile,
  currentView,
  onNavigate,
  selectedRepo,
  onSelectRepo,
  repositories,
  onOpenAddRepo,
  onOpenSearch,
  user,
  onLogout,
  onOpenAuth,
}) => {
  const userInitial = (user?.username || user?.email || "U").charAt(0).toUpperCase();

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isMobileOpen && (
        <div
          className="sidebar-mobile-backdrop"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      <aside
        className={`sidebar ${isOpen ? "sidebar-expanded" : "sidebar-collapsed"} ${
          isMobileOpen ? "sidebar-mobile-open" : ""
        }`}
      >
        {/* Brand Header */}
        <div className="sidebar-header">
          <div
            className="sidebar-brand"
            onClick={() => {
              onSelectRepo(null);
              onNavigate("repositories");
              onCloseMobile();
            }}
          >
            <div className="brand-icon-wrapper" style={{ flexShrink: 0 }}>
              <Cpu size={17} />
            </div>
            {isOpen && (
              <div className="sidebar-brand-text">
                <span className="brand-name">RepoMind</span>
                <span className="brand-badge" style={{ fontSize: "0.6rem" }}>
                  AI 2.0
                </span>
              </div>
            )}
          </div>

          {/* Desktop Toggle Button */}
          <button
            className="sidebar-toggle-btn desktop-only"
            onClick={onToggle}
            title={isOpen ? "Collapse Sidebar" : "Expand Sidebar"}
            aria-label={isOpen ? "Collapse Sidebar" : "Expand Sidebar"}
          >
            {isOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}
          </button>

          {/* Mobile Close Button */}
          <button
            className="sidebar-toggle-btn mobile-only"
            onClick={onCloseMobile}
            aria-label="Close Sidebar"
          >
            <X size={18} />
          </button>
        </div>

        {/* Action Buttons: Global Search & Add Repository */}
        <div style={{ padding: isOpen ? "0.65rem 0.85rem 0.45rem 0.85rem" : "0.65rem 0.4rem 0.45rem 0.4rem", display: "flex", flexDirection: "column", gap: "0.4rem" }}>
          {/* Global Search Trigger */}
          <button
            className="btn btn-outline"
            style={{
              width: "100%",
              justifyContent: isOpen ? "flex-start" : "center",
              padding: isOpen ? "0.45rem 0.65rem" : "0.45rem 0",
              fontSize: "0.8rem",
              borderRadius: "var(--radius-sm)",
              backgroundColor: "rgba(255, 255, 255, 0.03)",
              borderColor: "var(--border-subtle)",
              color: "var(--text-secondary)",
            }}
            onClick={() => {
              onOpenSearch();
              onCloseMobile();
            }}
            title="Global Search (⌘K)"
          >
            <Search size={15} style={{ flexShrink: 0 }} />
            {isOpen && (
              <span
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  flex: 1,
                  marginLeft: "0.45rem",
                }}
              >
                <span>Search...</span>
                <kbd
                  style={{
                    fontSize: "0.65rem",
                    fontFamily: "var(--font-mono)",
                    padding: "1px 5px",
                    borderRadius: "3px",
                    backgroundColor: "rgba(255, 255, 255, 0.06)",
                    border: "1px solid var(--border-subtle)",
                    color: "var(--text-muted)",
                  }}
                >
                  ⌘K
                </kbd>
              </span>
            )}
          </button>

          {/* Add Repository Button */}
          <button
            className="btn btn-primary"
            style={{
              width: "100%",
              justifyContent: isOpen ? "flex-start" : "center",
              padding: isOpen ? "0.45rem 0.65rem" : "0.45rem 0",
              fontSize: "0.8rem",
              borderRadius: "var(--radius-sm)",
            }}
            onClick={() => {
              onOpenAddRepo();
              onCloseMobile();
            }}
            title="Ingest New Repository"
          >
            <Plus size={15} style={{ flexShrink: 0 }} />
            {isOpen && <span style={{ marginLeft: "0.45rem" }}>Add Repository</span>}
          </button>
        </div>

        {/* Active Repository Context Widget (if a repo is selected) */}
        {selectedRepo && (
          <div
            style={{
              margin: isOpen ? "0 0.85rem 0.75rem 0.85rem" : "0 0.4rem 0.75rem 0.4rem",
              padding: isOpen ? "0.6rem 0.75rem" : "0.5rem 0.2rem",
              backgroundColor: "rgba(99, 102, 241, 0.08)",
              border: "1px solid rgba(99, 102, 241, 0.25)",
              borderRadius: "var(--radius-sm)",
            }}
          >
            {isOpen ? (
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontSize: "0.7rem",
                    color: "var(--text-muted)",
                    marginBottom: "0.25rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    fontWeight: 600,
                  }}
                >
                  <span>Active Project</span>
                  <button
                    onClick={() => {
                      onSelectRepo(null);
                      onNavigate("repositories");
                      onCloseMobile();
                    }}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#818cf8",
                      fontSize: "0.7rem",
                      cursor: "pointer",
                      padding: 0,
                    }}
                    title="Return to all repositories"
                  >
                    Change
                  </button>
                </div>
                <div
                  style={{
                    fontWeight: 700,
                    fontSize: "0.825rem",
                    color: "var(--text-primary)",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                  title={selectedRepo.full_name}
                >
                  {selectedRepo.name}
                </div>
                <div style={{ fontSize: "0.725rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                  {selectedRepo.owner}
                </div>
              </div>
            ) : (
              <div
                style={{ textAlign: "center" }}
                title={`Active: ${selectedRepo.full_name}`}
                onClick={() => {
                  onSelectRepo(null);
                  onNavigate("repositories");
                }}
              >
                <FolderGit2 size={16} color="#818cf8" style={{ margin: "0 auto" }} />
              </div>
            )}
          </div>
        )}

        {/* Navigation Sections */}
        <div className="sidebar-nav-scroll">
          <div className="sidebar-nav-group">
            {isOpen && <span className="sidebar-group-title">WORKSPACE</span>}

            {/* Repositories */}
            <button
              className={`sidebar-nav-item ${
                currentView === "repositories" && !selectedRepo ? "active" : ""
              }`}
              onClick={() => {
                onSelectRepo(null);
                onNavigate("repositories");
                onCloseMobile();
              }}
              title="All Repositories"
            >
              <FolderGit2 size={16} style={{ flexShrink: 0 }} />
              {isOpen && (
                <>
                  <span className="sidebar-item-label">Repositories</span>
                  <span className="sidebar-badge">{repositories.length}</span>
                </>
              )}
            </button>

            {/* Issues & Triage */}
            <button
              className={`sidebar-nav-item ${
                currentView === "issues" || (selectedRepo && currentView !== "pulls") ? "active" : ""
              }`}
              onClick={() => {
                if (selectedRepo) {
                  onNavigate("issues");
                } else if (repositories.length > 0) {
                  onSelectRepo(repositories[0]);
                  onNavigate("issues");
                } else {
                  onNavigate("repositories");
                }
                onCloseMobile();
              }}
              title="Issues & AI Triage"
            >
              <CircleDot size={16} style={{ flexShrink: 0 }} />
              {isOpen && (
                <>
                  <span className="sidebar-item-label">Issues & Triage</span>
                  {selectedRepo && (
                    <span className="sidebar-badge" style={{ backgroundColor: "rgba(99, 102, 241, 0.2)", color: "#a5b4fc" }}>
                      {selectedRepo.stored_issues_count ?? selectedRepo.open_issues_count}
                    </span>
                  )}
                </>
              )}
            </button>

            {/* Pull Requests */}
            <button
              className={`sidebar-nav-item ${currentView === "pulls" ? "active" : ""}`}
              onClick={() => {
                if (selectedRepo) {
                  onNavigate("pulls");
                } else if (repositories.length > 0) {
                  onSelectRepo(repositories[0]);
                  onNavigate("pulls");
                } else {
                  onNavigate("repositories");
                }
                onCloseMobile();
              }}
              title="Pull Requests & Diffs"
            >
              <GitPullRequest size={16} style={{ flexShrink: 0 }} />
              {isOpen && <span className="sidebar-item-label">Pull Requests</span>}
            </button>
          </div>

          {/* Quick Shortcuts Section when expanded */}
          {isOpen && repositories.length > 0 && (
            <div className="sidebar-nav-group" style={{ marginTop: "1rem" }}>
              <span className="sidebar-group-title">PINNED PROJECTS</span>
              {repositories.slice(0, 4).map((r) => {
                const isCurrent = selectedRepo?.id === r.id;
                return (
                  <button
                    key={r.id}
                    className={`sidebar-nav-item sidebar-sub-item ${isCurrent ? "active" : ""}`}
                    onClick={() => {
                      onSelectRepo(r);
                      onNavigate("issues");
                      onCloseMobile();
                    }}
                    title={r.full_name}
                  >
                    <span
                      style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        backgroundColor: isCurrent ? "#818cf8" : "var(--text-muted)",
                        flexShrink: 0,
                      }}
                    />
                    <span
                      className="sidebar-item-label"
                      style={{
                        fontSize: "0.8rem",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {r.name}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer / Engine Telemetry & User Session */}
        <div className="sidebar-footer">
          {/* Live Engine Status */}
          {isOpen ? (
            <div className="sidebar-status-box">
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <span className="status-dot-pulse" />
                <span style={{ fontSize: "0.725rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                  FastAPI Engine Online
                </span>
              </div>
              <span style={{ fontSize: "0.675rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                v1.0.0 • SQLite/PG
              </span>
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "0.5rem 0" }} title="Engine Online">
              <span className="status-dot-pulse" style={{ display: "inline-block" }} />
            </div>
          )}

          {/* User Account / Auth */}
          <div className="sidebar-user-box">
            {user ? (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", gap: "0.5rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", minWidth: 0 }}>
                  <div className="user-avatar-circle" style={{ flexShrink: 0 }}>
                    {userInitial}
                  </div>
                  {isOpen && (
                    <div style={{ minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: "0.8rem",
                          fontWeight: 600,
                          color: "var(--text-primary)",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {user.username || user.email.split("@")[0]}
                      </div>
                      <div
                        style={{
                          fontSize: "0.7rem",
                          color: "var(--text-muted)",
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {user.email}
                      </div>
                    </div>
                  )}
                </div>

                {isOpen && (
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={onLogout}
                    title="Sign Out"
                    style={{ padding: "4px 6px" }}
                  >
                    <LogOut size={14} />
                  </button>
                )}
              </div>
            ) : (
              <button
                className="btn btn-secondary btn-sm"
                style={{ width: "100%", justifyContent: "center" }}
                onClick={() => {
                  onOpenAuth("login");
                  onCloseMobile();
                }}
              >
                <LogIn size={14} />
                {isOpen && <span>Sign In</span>}
              </button>
            )}
          </div>
        </div>
      </aside>
    </>
  );
};
