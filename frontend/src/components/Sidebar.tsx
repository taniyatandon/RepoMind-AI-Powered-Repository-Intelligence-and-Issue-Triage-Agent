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

        {/* Active Repository Context Widget (if a repo is selected) */}
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
        </div>

        <div className="sidebar-footer">
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
