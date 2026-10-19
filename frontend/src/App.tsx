import React, { useEffect, useState } from "react";
import {
  apiDeleteRepository,
  apiGetIssueDetails,
  apiGetMe,
  apiGetRepository,
  apiListRepositories,
  apiSyncRepository,
  clearAuthToken,
  getAuthToken,
  getStoredUser,
} from "./api";
import { AddRepositoryModal } from "./components/AddRepositoryModal";
import { AuthModal } from "./components/AuthModal";
import { CommandPalette } from "./components/CommandPalette";
import { IssueDetailModal } from "./components/IssueDetailModal";
import { IssueExplorer } from "./components/IssueExplorer";
import { Navbar } from "./components/Navbar";
import { RepositoryList } from "./components/RepositoryList";
import { Sidebar } from "./components/Sidebar";
import {
  Issue,
  Repository,
  SearchResultInvestigation,
  SearchResultIssue,
  SearchResultPullRequest,
  SearchResultRepository,
  User,
} from "./types";
import {
  AlertCircle,
  CheckCircle2,
  Cpu,
  GitBranch,
  Shield,
  X,
} from "lucide-react";

export const App: React.FC = () => {
  const [user, setUser] = useState<User | null>(getStoredUser());
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [addRepoModalOpen, setAddRepoModalOpen] = useState(false);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [currentView, setCurrentView] = useState<"repositories" | "issues" | "pulls">("repositories");
  const [searchPaletteOpen, setSearchPaletteOpen] = useState(false);

  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [reposLoading, setReposLoading] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);
  const [selectedIssue, setSelectedIssue] = useState<Issue | null>(null);

  const [notification, setNotification] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  const showNotification = (type: "success" | "error", message: string) => {
    setNotification({ type, message });
    setTimeout(() => {
      setNotification((curr) => (curr?.message === message ? null : curr));
    }, 4500);
  };

  // Check auth and load repositories
  useEffect(() => {
    const token = getAuthToken();
    if (token) {
      apiGetMe()
        .then((fetchedUser) => {
          setUser(fetchedUser);
          loadRepositories();
        })
        .catch(() => {
          clearAuthToken();
          setUser(null);
        });
    } else {
      // Auto open login dialog for immediate testing
      setAuthModalOpen(true);
    }

    const handleUnauthorized = () => {
      setUser(null);
      setAuthModalOpen(true);
      showNotification("error", "Session expired. Please log in.");
    };

    window.addEventListener("repomind_unauthorized", handleUnauthorized);
    return () => {
      window.removeEventListener("repomind_unauthorized", handleUnauthorized);
    };
  }, []);

  // Global Keyboard shortcut handler (⌘K or Ctrl+K for Global Search)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        if (authModalOpen || addRepoModalOpen) {
          return;
        }
        e.preventDefault();
        if (!user) {
          setAuthMode("login");
          setAuthModalOpen(true);
        } else {
          setSearchPaletteOpen((prev) => !prev);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [user, authModalOpen, addRepoModalOpen]);

  const loadRepositories = async () => {
    setReposLoading(true);
    try {
      const data = await apiListRepositories();
      setRepositories(data);
    } catch (err: any) {
      console.warn("Failed to load repositories:", err);
    } finally {
      setReposLoading(false);
    }
  };

  const handleAuthSuccess = (authenticatedUser: User) => {
    setUser(authenticatedUser);
    showNotification("success", `Welcome back, ${authenticatedUser.username || authenticatedUser.email}!`);
    loadRepositories();
  };

  const handleLogout = () => {
    clearAuthToken();
    setUser(null);
    setSelectedRepo(null);
    setRepositories([]);
    showNotification("success", "You have been logged out.");
  };

  const handleSyncRepo = async (repo: Repository) => {
    try {
      await apiSyncRepository(repo.id);
      showNotification(
        "success",
        `Sync job started for ${repo.full_name}. Background ingestion active...`
      );
      // Refresh list after brief moment
      setTimeout(loadRepositories, 3000);
    } catch (err: any) {
      showNotification("error", err.message || "Failed to trigger sync.");
    }
  };

  const handleDeleteRepo = async (repo: Repository) => {
    try {
      await apiDeleteRepository(repo.id);
      showNotification("success", `Repository ${repo.full_name} removed.`);
      if (selectedRepo?.id === repo.id) {
        setSelectedRepo(null);
      }
      loadRepositories();
    } catch (err: any) {
      showNotification("error", err.message || "Failed to delete repository.");
    }
  };

  const handleQuickIngest = (_repoUrlOrName: string) => {
    if (!user) {
      setAuthMode("login");
      setAuthModalOpen(true);
    } else {
      setAddRepoModalOpen(true);
    }
  };

  const handleSelectSearchResultRepo = async (repoResult: SearchResultRepository) => {
    const existing = repositories.find((r) => r.id === repoResult.id);
    if (existing) {
      setSelectedRepo(existing);
    } else {
      try {
        const fullRepo = await apiGetRepository(repoResult.id);
        setSelectedRepo(fullRepo);
      } catch {
        setSelectedRepo({
          id: repoResult.id,
          github_repo_id: 0,
          full_name: repoResult.full_name,
          name: repoResult.name,
          owner: repoResult.owner,
          description: repoResult.description,
          html_url: `https://github.com/${repoResult.full_name}`,
          language: repoResult.language,
          stargazers_count: repoResult.stargazers_count,
          forks_count: 0,
          open_issues_count: repoResult.open_issues_count,
          last_synced_at: null,
          created_at: new Date().toISOString(),
        });
      }
    }
    setCurrentView("issues");
    setSearchPaletteOpen(false);
  };

  const handleSelectSearchResultIssue = async (issueResult: SearchResultIssue) => {
    try {
      const parentRepo =
        repositories.find((r) => r.id === issueResult.repository_id) ||
        (await apiGetRepository(issueResult.repository_id));
      setSelectedRepo(parentRepo);
      setCurrentView("issues");

      const fullIssue = await apiGetIssueDetails(issueResult.id);
      setSelectedIssue(fullIssue);
    } catch (err) {
      console.warn("Failed to load issue destination:", err);
      showNotification("error", "Failed to navigate to issue.");
    }
    setSearchPaletteOpen(false);
  };

  const handleSelectSearchResultPR = async (prResult: SearchResultPullRequest) => {
    try {
      const parentRepo =
        repositories.find((r) => r.id === prResult.repository_id) ||
        (await apiGetRepository(prResult.repository_id));
      setSelectedRepo(parentRepo);
      setCurrentView("pulls");
    } catch (err) {
      console.warn("Failed to load PR destination:", err);
      showNotification("error", "Failed to navigate to pull request.");
    }
    setSearchPaletteOpen(false);
  };

  const handleSelectInvestigation = async (invResult: SearchResultInvestigation) => {
    try {
      const parentRepo =
        repositories.find((r) => r.id === invResult.repository_id) ||
        (await apiGetRepository(invResult.repository_id));
      setSelectedRepo(parentRepo);
      setCurrentView("issues");

      const fullIssue = await apiGetIssueDetails(invResult.issue_id);
      setSelectedIssue(fullIssue);
    } catch (err) {
      console.warn("Failed to load investigation issue:", err);
      showNotification("error", "Failed to navigate to investigated issue.");
    }
    setSearchPaletteOpen(false);
  };

  return (
    <div className="app-layout">
      {/* Collapsible Developer Workspace Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen((prev) => !prev)}
        isMobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
        currentView={currentView}
        onNavigate={(view) => {
          setCurrentView(view);
          if (view === "repositories") {
            setSelectedRepo(null);
          }
        }}
        selectedRepo={selectedRepo}
        onSelectRepo={(repo) => {
          setSelectedRepo(repo);
          if (repo) {
            if (currentView === "repositories") {
              setCurrentView("issues");
            }
          } else {
            setCurrentView("repositories");
          }
        }}
        repositories={repositories}
        onOpenAddRepo={() => {
          if (!user) {
            setAuthMode("login");
            setAuthModalOpen(true);
          } else {
            setAddRepoModalOpen(true);
          }
        }}
        onOpenSearch={() => {
          if (!user) {
            setAuthMode("login");
            setAuthModalOpen(true);
          } else {
            setSearchPaletteOpen(true);
          }
        }}
        user={user}
        onLogout={handleLogout}
        onOpenAuth={(mode) => {
          setAuthMode(mode);
          setAuthModalOpen(true);
        }}
      />

      <div className="app-main-pane">
        <Navbar
          user={user}
          activeRepo={selectedRepo}
          onOpenAuth={(mode) => {
            setAuthMode(mode);
            setAuthModalOpen(true);
          }}
          onLogout={handleLogout}
          onOpenAddRepo={() => {
            if (!user) {
              setAuthMode("login");
              setAuthModalOpen(true);
            } else {
              setAddRepoModalOpen(true);
            }
          }}
          onOpenSearch={() => {
            if (!user) {
              setAuthMode("login");
              setAuthModalOpen(true);
            } else {
              setSearchPaletteOpen(true);
            }
          }}
          onGoHome={() => {
            setSelectedRepo(null);
            setCurrentView("repositories");
          }}
          onToggleMobileSidebar={() => setMobileSidebarOpen(true)}
        />

        <main className="main-content">
          {/* Global Floating Toast Notification */}
          {notification && (
            <div
              style={{
                position: "fixed",
                bottom: "1.5rem",
                right: "1.5rem",
                zIndex: 100,
                maxWidth: "420px",
                boxShadow: "var(--shadow-lg), 0 0 24px rgba(0, 0, 0, 0.6)",
                animation: "fadeIn 0.2s ease-out",
              }}
            >
              <div
                className={`alert ${
                  notification.type === "success" ? "alert-success" : "alert-danger"
                }`}
                style={{
                  margin: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "0.75rem 1rem",
                  borderRadius: "var(--radius-sm)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
                  {notification.type === "success" ? (
                    <CheckCircle2 size={18} style={{ flexShrink: 0 }} />
                  ) : (
                    <AlertCircle size={18} style={{ flexShrink: 0 }} />
                  )}
                  <span style={{ fontSize: "0.85rem", fontWeight: 500 }}>
                    {notification.message}
                  </span>
                </div>
                <button
                  onClick={() => setNotification(null)}
                  style={{
                    background: "none",
                    border: "none",
                    color: "inherit",
                    cursor: "pointer",
                    padding: "2px",
                    marginLeft: "0.75rem",
                    display: "flex",
                    alignItems: "center",
                    opacity: 0.8,
                  }}
                >
                  <X size={14} />
                </button>
              </div>
            </div>
          )}

          {/* View Switcher: Repository List or Issue Explorer */}
          {selectedRepo ? (
            <IssueExplorer
              repository={selectedRepo}
              onBack={() => {
                setSelectedRepo(null);
                setCurrentView("repositories");
                loadRepositories();
              }}
              onSelectIssue={(issue) => setSelectedIssue(issue)}
              onSyncRepo={() => handleSyncRepo(selectedRepo)}
              initialTab={currentView === "pulls" ? "pulls" : "issues"}
              onTabChange={(tab) => setCurrentView(tab)}
            />
          ) : (
            <RepositoryList
              repositories={repositories}
              loading={reposLoading}
              onSelectRepo={(repo) => {
                setSelectedRepo(repo);
                setCurrentView("issues");
              }}
              onDeleteRepo={handleDeleteRepo}
              onSyncRepo={handleSyncRepo}
              onOpenAddRepo={() => {
                if (!user) {
                  setAuthMode("login");
                  setAuthModalOpen(true);
                } else {
                  setAddRepoModalOpen(true);
                }
              }}
              onQuickIngest={handleQuickIngest}
            />
          )}
        </main>

        {/* Modern Developer Workspace Footer */}
        <footer
          style={{
            borderTop: "1px solid var(--border-subtle)",
            padding: "1.5rem 1.5rem",
            backgroundColor: "rgba(10, 15, 29, 0.7)",
            marginTop: "auto",
          }}
        >
          <div
            style={{
              maxWidth: "1360px",
              margin: "0 auto",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "1rem",
              fontSize: "0.8rem",
              color: "var(--text-muted)",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
              <span style={{ fontWeight: 600, color: "var(--text-secondary)" }}>RepoMind</span>
              <span>•</span>
              <span>Open-Source Repository Intelligence & Issue Triage Agent</span>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "1.25rem" }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                <Shield size={13} color="#10b981" />
                <span>JWT Bearer Auth</span>
              </span>
              <span style={{ display: "inline-flex", alignItems: "center", gap: "0.35rem" }}>
                <Cpu size={13} color="#6366f1" />
                <span>FastAPI REST API</span>
              </span>
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
                style={{
                  color: "var(--text-muted)",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.3rem",
                  textDecoration: "none",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
                onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
              >
                <GitBranch size={13} />
                <span>GitHub API</span>
              </a>
            </div>
          </div>
        </footer>
      </div>

      {/* Modals */}
      <AuthModal
        initialMode={authMode}
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        onSuccess={handleAuthSuccess}
      />

      <AddRepositoryModal
        isOpen={addRepoModalOpen}
        onClose={() => setAddRepoModalOpen(false)}
        onSuccess={() => {
          showNotification("success", "Repository successfully ingested!");
          loadRepositories();
        }}
      />

      <IssueDetailModal
        issue={selectedIssue}
        onClose={() => setSelectedIssue(null)}
      />

      {/* Global Search & Command Palette Modal */}
      <CommandPalette
        isOpen={searchPaletteOpen}
        onClose={() => setSearchPaletteOpen(false)}
        onSelectRepository={handleSelectSearchResultRepo}
        onSelectIssue={handleSelectSearchResultIssue}
        onSelectPullRequest={handleSelectSearchResultPR}
        onSelectInvestigation={handleSelectInvestigation}
        repositories={repositories}
        activeRepo={selectedRepo}
      />
    </div>
  );
};
