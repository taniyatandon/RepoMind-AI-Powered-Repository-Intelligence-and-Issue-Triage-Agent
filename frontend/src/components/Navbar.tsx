import React from "react";
import { Repository, User } from "../types";
import {
  ChevronRight,
  Cpu,
  FolderGit2,
  LogIn,
  LogOut,
  Menu,
  Plus,
  Search,
  User as UserIcon,
} from "lucide-react";

interface NavbarProps {
  user: User | null;
  onOpenAuth: (mode: "login" | "register") => void;
  onLogout: () => void;
  onOpenAddRepo: () => void;
  onGoHome: () => void;
  activeRepo?: Repository | null;
  onToggleMobileSidebar?: () => void;
  onOpenSearch: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  onOpenAuth,
  onLogout,
  onOpenAddRepo,
  onGoHome,
  activeRepo,
  onToggleMobileSidebar,
  onOpenSearch,
}) => {
  const userInitial = (user?.username || user?.email || "U").charAt(0).toUpperCase();

  return (
    <header className="navbar">
      <div className="navbar-inner">
        {/* Left: Mobile Menu Toggle & Brand / Breadcrumb */}
        <div style={{ display: "flex", alignItems: "center", gap: "0.85rem" }}>
          {onToggleMobileSidebar && (
            <button
              className="btn btn-ghost btn-sm mobile-only"
              onClick={onToggleMobileSidebar}
              aria-label="Open Navigation Menu"
              style={{ padding: "0.35rem" }}
            >
              <Menu size={18} />
            </button>
          )}

          <div className="brand" onClick={onGoHome} title="RepoMind Home">
            <div className="brand-icon-wrapper">
              <Cpu size={18} />
            </div>
            <div className="brand-text">
              <span>RepoMind</span>
              <span className="brand-badge">AI 2.0</span>
            </div>
          </div>

          {activeRepo && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0.4rem",
                fontSize: "0.825rem",
                color: "var(--text-secondary)",
              }}
              className="desktop-breadcrumb"
            >
              <ChevronRight size={13} color="var(--text-muted)" />
              <button
                onClick={onGoHome}
                style={{
                  background: "none",
                  border: "none",
                  color: "var(--text-muted)",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.3rem",
                  fontSize: "0.8rem",
                  padding: "2px 4px",
                  borderRadius: "4px",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
              >
                <FolderGit2 size={13} />
                <span>Repositories</span>
              </button>
              <ChevronRight size={13} color="var(--text-muted)" />
              <span
                style={{
                  fontWeight: 600,
                  color: "var(--text-primary)",
                  fontFamily: "var(--font-mono)",
                  fontSize: "0.8rem",
                  backgroundColor: "rgba(255, 255, 255, 0.04)",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                {activeRepo.full_name}
              </span>
            </div>
          )}
        </div>

        {/* Center: Global Search Trigger Field */}
        <div className="navbar-search-container">
          <button
            className="navbar-search-btn"
            onClick={onOpenSearch}
            title="Global search across repositories, issues, and pull requests (⌘K)"
            aria-label="Search repositories, issues, pull requests (⌘K)"
          >
            <Search size={14} className="navbar-search-icon" />
            <span className="navbar-search-placeholder">
              Search repositories, issues, pull requests...
            </span>
            <kbd className="navbar-search-kbd">
              <span>⌘K</span>
            </kbd>
          </button>
        </div>

        {/* Right: Actions & User Session */}
        <div className="nav-actions">
          {user ? (
            <>
              <button
                className="btn btn-primary btn-sm"
                onClick={onOpenAddRepo}
                title="Add new GitHub repository"
              >
                <Plus size={15} />
                <span>Add Repository</span>
              </button>

              <div className="user-badge" title={`Signed in as ${user.email}`}>
                <div className="user-avatar-circle">
                  {userInitial}
                </div>
                <span
                  style={{
                    maxWidth: "140px",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {user.username || user.email}
                </span>
              </div>

              <button
                className="btn btn-ghost btn-sm"
                onClick={onLogout}
                title="Log out from RepoMind"
                style={{ padding: "0.35rem 0.5rem" }}
              >
                <LogOut size={15} />
              </button>
            </>
          ) : (
            <>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => onOpenAuth("login")}
              >
                <LogIn size={15} />
                <span>Log In</span>
              </button>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => onOpenAuth("register")}
              >
                <UserIcon size={14} />
                <span>Sign Up</span>
              </button>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
