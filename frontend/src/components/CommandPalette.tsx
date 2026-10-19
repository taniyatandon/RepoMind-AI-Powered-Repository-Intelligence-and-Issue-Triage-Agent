import React, { useEffect, useMemo, useRef, useState } from "react";
import { apiExplainCode, apiGlobalSearch } from "../api";
import {
  AIExplanationResponse,
  CodeCitation,
  GlobalSearchResponse,
  Repository,
  SearchMode,
  SearchResultCodeChunk,
  SearchResultInvestigation,
  SearchResultIssue,
  SearchResultPullRequest,
  SearchResultRepository,
} from "../types";
import {
  AlertCircle,
  ArrowRight,
  Bot,
  Check,
  CheckCircle2,
  CircleDot,
  Code2,
  CornerDownLeft,
  Copy,
  FileCode,
  FolderGit2,
  GitPullRequest,
  Layers,
  Lightbulb,
  Loader2,
  Search,
  SearchX,
  Sparkles,
  Star,
  X,
} from "lucide-react";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectRepository: (repo: SearchResultRepository) => void;
  onSelectIssue: (issue: SearchResultIssue) => void;
  onSelectPullRequest: (pr: SearchResultPullRequest) => void;
  onSelectInvestigation?: (inv: SearchResultInvestigation) => void;
  repositories?: Repository[];
  activeRepo?: Repository | null;
}

type NavigableItem =
  | { kind: "code_chunk"; item: SearchResultCodeChunk }
  | { kind: "investigation"; item: SearchResultInvestigation }
  | { kind: "repository"; item: SearchResultRepository }
  | { kind: "issue"; item: SearchResultIssue }
  | { kind: "pull_request"; item: SearchResultPullRequest };

// Helper component to highlight matching search tokens safely
const HighlightText: React.FC<{ text: string | null | undefined; query: string }> = ({
  text,
  query,
}) => {
  if (!text) return null;
  const cleanQ = query.trim().replace(/^#/, "");
  if (!cleanQ || cleanQ.length < 2) return <>{text}</>;

  try {
    const escaped = cleanQ.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${escaped})`, "gi");
    const parts = text.split(regex);

    return (
      <>
        {parts.map((part, index) =>
          regex.test(part) ? (
            <span key={index} className="search-highlight">
              {part}
            </span>
          ) : (
            <span key={index}>{part}</span>
          )
        )}
      </>
    );
  } catch {
    return <>{text}</>;
  }
};

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectRepository,
  onSelectIssue,
  onSelectPullRequest,
  onSelectInvestigation,
  repositories = [],
  activeRepo = null,
}) => {
  const [query, setQuery] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("all");
  const [selectedRepoId, setSelectedRepoId] = useState<number | null>(activeRepo?.id || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<GlobalSearchResponse | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Grounded AI explanation state
  const [explanation, setExplanation] = useState<AIExplanationResponse | null>(null);
  const [explaining, setExplaining] = useState(false);
  const [explanationError, setExplanationError] = useState<string | null>(null);
  const [copiedCitationIdx, setCopiedCitationIdx] = useState<number | null>(null);
  const [expandedChunkId, setExpandedChunkId] = useState<number | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const listContainerRef = useRef<HTMLDivElement>(null);

  // Sync active repo if changed
  useEffect(() => {
    if (activeRepo) {
      setSelectedRepoId(activeRepo.id);
    }
  }, [activeRepo]);

  // Flattened items for unified arrow key navigation
  const flattenedItems = useMemo<NavigableItem[]>(() => {
    if (!results || explanation) return [];
    const list: NavigableItem[] = [];

    if (results.code_chunks && results.code_chunks.length > 0) {
      results.code_chunks.forEach((c) => list.push({ kind: "code_chunk", item: c }));
    }
    if (results.investigations && results.investigations.length > 0) {
      results.investigations.forEach((inv) => list.push({ kind: "investigation", item: inv }));
    }
    if (results.repositories && results.repositories.length > 0) {
      results.repositories.forEach((r) => list.push({ kind: "repository", item: r }));
    }
    if (results.issues && results.issues.length > 0) {
      results.issues.forEach((i) => list.push({ kind: "issue", item: i }));
    }
    if (results.pull_requests && results.pull_requests.length > 0) {
      results.pull_requests.forEach((p) => list.push({ kind: "pull_request", item: p }));
    }
    return list;
  }, [results, explanation]);

  // Reset state and focus on open
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setResults(null);
      setError(null);
      setExplanation(null);
      setExplanationError(null);
      setSelectedIndex(0);
      setTimeout(() => {
        inputRef.current?.focus();
      }, 60);
    } else {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    }
  }, [isOpen]);

  // Keep selected index within bounds
  useEffect(() => {
    if (flattenedItems.length === 0) {
      setSelectedIndex(0);
    } else if (selectedIndex >= flattenedItems.length) {
      setSelectedIndex(flattenedItems.length - 1);
    }
  }, [flattenedItems, selectedIndex]);

  // Perform search query with debounce
  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults(null);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    const debounceTimer = setTimeout(async () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const data = await apiGlobalSearch(
          trimmed,
          6,
          searchMode,
          selectedRepoId || undefined,
          controller.signal
        );
        setResults(data);
        setSelectedIndex(0);
      } catch (err: any) {
        if (err.name === "AbortError") {
          return;
        }
        console.warn("Search request failed:", err);
        setError(err.message || "Failed to search codebase and repositories.");
      } finally {
        setLoading(false);
      }
    }, 220);

    return () => {
      clearTimeout(debounceTimer);
    };
  }, [query, searchMode, selectedRepoId]);

  // Action execution on selection
  const handleSelect = (navItem: NavigableItem) => {
    if (navItem.kind === "repository") {
      onSelectRepository(navItem.item);
      onClose();
    } else if (navItem.kind === "issue") {
      onSelectIssue(navItem.item);
      onClose();
    } else if (navItem.kind === "pull_request") {
      onSelectPullRequest(navItem.item);
      onClose();
    } else if (navItem.kind === "investigation") {
      if (onSelectInvestigation) {
        onSelectInvestigation(navItem.item);
      } else {
        // Fallback: construct an issue item
        onSelectIssue({
          id: navItem.item.issue_id,
          type: "issue",
          repository_id: navItem.item.repository_id,
          repository_name: navItem.item.repository_name,
          issue_number: navItem.item.issue_number,
          title: navItem.item.issue_title,
          state: "open",
          comments_count: 0,
          labels: [],
        });
      }
      onClose();
    } else if (navItem.kind === "code_chunk") {
      // Toggle expansion for code chunk preview
      setExpandedChunkId((prev) => (prev === navItem.item.id ? null : navItem.item.id));
    }
  };

  // Trigger grounded AI explanation
  const handleAskAIExplanation = async (targetQuery?: string) => {
    const q = (targetQuery || query).trim();
    if (!q) return;

    setExplaining(true);
    setExplanationError(null);
    try {
      const data = await apiExplainCode(q, selectedRepoId || undefined);
      setExplanation(data);
    } catch (err: any) {
      console.warn("AI explanation failed:", err);
      setExplanationError(err.message || "Failed to generate grounded AI code explanation.");
    } finally {
      setExplaining(false);
    }
  };

  // Keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      if (explanation) {
        setExplanation(null);
      } else {
        onClose();
      }
    } else if (e.key === "Tab") {
      e.preventDefault();
      const modes: SearchMode[] = ["all", "code", "investigations", "keyword"];
      const curIdx = modes.indexOf(searchMode);
      const nextIdx = e.shiftKey
        ? (curIdx - 1 + modes.length) % modes.length
        : (curIdx + 1) % modes.length;
      setSearchMode(modes[nextIdx]);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (flattenedItems.length > 0) {
        setSelectedIndex((prev) => (prev + 1) % flattenedItems.length);
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (flattenedItems.length > 0) {
        setSelectedIndex((prev) => (prev - 1 + flattenedItems.length) % flattenedItems.length);
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (flattenedItems.length > 0 && flattenedItems[selectedIndex]) {
        handleSelect(flattenedItems[selectedIndex]);
      } else if (query.trim()) {
        handleAskAIExplanation();
      }
    }
  };

  const copyCitation = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedCitationIdx(index);
    setTimeout(() => setCopiedCitationIdx(null), 1800);
  };

  const getPlaceholder = () => {
    switch (searchMode) {
      case "code":
        return "Ask about code logic, patterns, auth, APIs (e.g. 'how are JWT tokens decoded?')...";
      case "investigations":
        return "Search past AI diagnoses, root-causes, errors (e.g. 'KeyError', 'sub claim')...";
      case "keyword":
        return "Search repository names, issue titles, PR titles by keyword...";
      default:
        return "Search code, AI investigations, issues, PRs, and repositories...";
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="command-palette-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-label="Global Search and AI Code Intelligence"
    >
      <div className="command-palette-card" onKeyDown={handleKeyDown}>
        {/* Search Input Bar */}
        <div className="command-palette-header">
          <Search size={18} className="command-palette-search-icon" />
          <input
            ref={inputRef}
            type="text"
            className="command-palette-input"
            placeholder={getPlaceholder()}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              if (explanation) setExplanation(null);
            }}
            aria-label="Search repositories, code, and issues"
          />
          {loading && <Loader2 size={16} className="spinner" style={{ color: "var(--color-primary)" }} />}
          {query && !loading && (
            <button
              className="command-palette-clear-btn"
              onClick={() => {
                setQuery("");
                setResults(null);
                setExplanation(null);
                inputRef.current?.focus();
              }}
              aria-label="Clear search input"
              title="Clear search"
            >
              <X size={14} />
            </button>
          )}
          <span className="command-palette-esc-badge">ESC</span>
        </div>

        {/* Phase 2: Mode Selector & Scope Bar */}
        <div className="command-palette-toolbar">
          <div className="search-mode-tabs" role="tablist">
            <button
              type="button"
              role="tab"
              aria-selected={searchMode === "all"}
              className={`search-mode-tab ${searchMode === "all" ? "active" : ""}`}
              onClick={() => setSearchMode("all")}
            >
              <Layers size={13} />
              <span>All</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={searchMode === "code"}
              className={`search-mode-tab ${searchMode === "code" ? "active" : ""}`}
              onClick={() => setSearchMode("code")}
            >
              <FileCode size={13} />
              <span>Code (Semantic)</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={searchMode === "investigations"}
              className={`search-mode-tab ${searchMode === "investigations" ? "active" : ""}`}
              onClick={() => setSearchMode("investigations")}
            >
              <Lightbulb size={13} />
              <span>Investigations</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={searchMode === "keyword"}
              className={`search-mode-tab ${searchMode === "keyword" ? "active" : ""}`}
              onClick={() => setSearchMode("keyword")}
            >
              <Search size={13} />
              <span>Keyword</span>
            </button>
          </div>

          {/* Scope Dropdown */}
          {repositories.length > 0 && (
            <div className="search-scope-wrapper">
              <select
                className="search-scope-select"
                value={selectedRepoId || ""}
                onChange={(e) => setSelectedRepoId(e.target.value ? Number(e.target.value) : null)}
                title="Filter search to specific repository"
              >
                <option value="">All Projects ({repositories.length})</option>
                {repositories.map((repo) => (
                  <option key={repo.id} value={repo.id}>
                    {repo.name} ({repo.owner})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Content Body */}
        <div className="command-palette-body" ref={listContainerRef}>
          {/* Error Message */}
          {error && (
            <div className="command-palette-error">
              <AlertCircle size={15} style={{ flexShrink: 0, marginTop: "2px" }} />
              <span>{error}</span>
            </div>
          )}
          {explanationError && (
            <div className="command-palette-error">
              <AlertCircle size={15} style={{ flexShrink: 0, marginTop: "2px" }} />
              <span>{explanationError}</span>
            </div>
          )}

          {/* Grounded AI Explanation View */}
          {explanation && (
            <div className="grounded-ai-explanation-panel">
              <div className="ai-explanation-header">
                <div className="ai-badge-group">
                  <div className="ai-assistant-badge">
                    <Sparkles size={14} />
                    <span>RepoMind Code Intelligence</span>
                  </div>
                  {explanation.evidence_sufficient ? (
                    <span className="badge badge-success" style={{ fontSize: "0.725rem", display: "inline-flex", alignItems: "center", gap: "0.3rem" }}>
                      <CheckCircle2 size={12} />
                      Grounded • {explanation.citations.length} Citations
                    </span>
                  ) : (
                    <span className="badge" style={{ fontSize: "0.725rem", backgroundColor: "rgba(245, 158, 11, 0.15)", color: "#fbbf24", border: "1px solid rgba(245, 158, 11, 0.3)" }}>
                      Limited Evidence
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  className="btn btn-ghost btn-xs"
                  onClick={() => setExplanation(null)}
                  style={{ color: "var(--text-muted)" }}
                >
                  <ArrowRight size={13} /> Back to Search Results
                </button>
              </div>

              <div className="ai-explanation-answer">
                <p style={{ whiteSpace: "pre-line", lineHeight: 1.6, color: "var(--text-primary)", fontSize: "0.875rem", margin: 0 }}>
                  {explanation.answer}
                </p>
              </div>

              {/* Citations & Evidence Chunks */}
              {explanation.citations.length > 0 && (
                <div className="ai-citations-container">
                  <div className="ai-citations-title">
                    <Code2 size={13} />
                    <span>VERIFIED CODE CITATIONS ({explanation.citations.length})</span>
                  </div>
                  <div className="ai-citations-list">
                    {explanation.citations.map((cite: CodeCitation, idx: number) => {
                      const isCopied = copiedCitationIdx === idx;
                      return (
                        <div key={idx} className="ai-citation-card">
                          <div className="ai-citation-meta">
                            <span className="citation-path">
                              <FileCode size={13} color="#818cf8" />
                              <strong>{cite.file_path}</strong>
                              <span className="citation-lines">L{cite.start_line}-L{cite.end_line}</span>
                            </span>
                            <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                              <span className="citation-score">
                                {(cite.relevance * 100).toFixed(0)}% match
                              </span>
                              <button
                                type="button"
                                className="citation-copy-btn"
                                onClick={() => copyCitation(cite.snippet, idx)}
                                title="Copy code snippet"
                              >
                                {isCopied ? <Check size={12} color="#34d399" /> : <Copy size={12} />}
                              </button>
                            </div>
                          </div>
                          <pre className="citation-snippet">
                            <code>{cite.snippet}</code>
                          </pre>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* AI Explaining Loader */}
          {explaining && (
            <div className="command-palette-loading-state">
              <Loader2 size={24} className="spinner" style={{ color: "#818cf8", marginBottom: "0.75rem" }} />
              <div style={{ fontWeight: 600, color: "var(--text-primary)", fontSize: "0.9rem" }}>
                Synthesizing Grounded Code Explanation...
              </div>
              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                Retrieving verified code chunks and citing line ranges
              </span>
            </div>
          )}

          {/* Ask AI Explanation Trigger Banner */}
          {!explanation && !explaining && query.trim() && (
            <div className="ai-ask-banner" onClick={() => handleAskAIExplanation()}>
              <div className="ai-ask-left">
                <div className="ai-ask-icon-box">
                  <Sparkles size={16} />
                </div>
                <div>
                  <div className="ai-ask-title">
                    Ask AI: "{query.trim()}"
                  </div>
                  <div className="ai-ask-subtitle">
                    Generate an evidence-backed architectural explanation with verified line citations
                  </div>
                </div>
              </div>
              <button
                type="button"
                className="btn btn-primary btn-xs"
                onClick={(e) => {
                  e.stopPropagation();
                  handleAskAIExplanation();
                }}
              >
                <span>Explain</span>
                <CornerDownLeft size={12} />
              </button>
            </div>
          )}

          {/* Initial State (No query yet) */}
          {!query.trim() && !loading && !explanation && (
            <div className="command-palette-guide">
              <div className="command-palette-guide-title">EXPLORE REPOMIND CAPABILITIES</div>
              <div className="command-palette-guide-grid">
                <div
                  className="guide-item clickable"
                  onClick={() => {
                    setSearchMode("code");
                    setQuery("authentication token validation");
                  }}
                >
                  <div className="guide-icon-box" style={{ background: "rgba(99, 102, 241, 0.15)", color: "#818cf8" }}>
                    <FileCode size={15} />
                  </div>
                  <div>
                    <div className="guide-item-title">Semantic Code Search</div>
                    <div className="guide-item-desc">Find implementations by concept (e.g. "JWT auth", "diff parser")</div>
                  </div>
                </div>
                <div
                  className="guide-item clickable"
                  onClick={() => {
                    setSearchMode("investigations");
                    setQuery("KeyError");
                  }}
                >
                  <div className="guide-icon-box" style={{ background: "rgba(245, 158, 11, 0.15)", color: "#fbbf24" }}>
                    <Lightbulb size={15} />
                  </div>
                  <div>
                    <div className="guide-item-title">AI Investigations History</div>
                    <div className="guide-item-desc">Search past root-cause diagnoses, bug priorities & hypotheses</div>
                  </div>
                </div>
                <div
                  className="guide-item clickable"
                  onClick={() => {
                    setSearchMode("all");
                    setQuery("fastapi");
                  }}
                >
                  <div className="guide-icon-box" style={{ background: "rgba(52, 211, 153, 0.15)", color: "#34d399" }}>
                    <FolderGit2 size={15} />
                  </div>
                  <div>
                    <div className="guide-item-title">Repositories & Issues</div>
                    <div className="guide-item-desc">Search synchronized projects, open issues, and pull requests</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Loading Indicator */}
          {loading && !results && !explanation && !explaining && (
            <div className="command-palette-loading-state">
              <Loader2 size={24} className="spinner" style={{ color: "#818cf8", marginBottom: "0.5rem" }} />
              <span>Scanning codebase, investigations, and repository metadata...</span>
            </div>
          )}

          {/* Empty Results State */}
          {query.trim() && !loading && !explanation && !explaining && results && results.total === 0 && (
            <div className="command-palette-empty-state">
              <SearchX size={32} style={{ color: "var(--text-muted)", marginBottom: "0.75rem" }} />
              <div className="empty-title">No results found for "{query}"</div>
              <div className="empty-subtitle">
                {searchMode === "code"
                  ? "No matching code chunks found. Ensure the repository has been indexed via 'Index Code'."
                  : "No matching items found in your synchronized projects."}
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => handleAskAIExplanation()}
                style={{ marginTop: "0.75rem" }}
              >
                <Sparkles size={13} />
                <span>Ask AI to investigate codebase</span>
              </button>
            </div>
          )}

          {/* Categorized Results */}
          {!explanation && !explaining && results && results.total > 0 && (
            <div className="command-palette-results">
              {/* 1. Code Chunks Category (Semantic Code Intelligence) */}
              {results.code_chunks && results.code_chunks.length > 0 && (
                <div className="command-category-group">
                  <div className="command-category-header">
                    <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                      <FileCode size={13} color="#818cf8" />
                      SOURCE CODE MATCHES
                    </span>
                    <span className="category-count">{results.code_chunks.length}</span>
                  </div>
                  {results.code_chunks.map((chunk) => {
                    const itemIndex = flattenedItems.findIndex(
                      (i) => i.kind === "code_chunk" && i.item.id === chunk.id
                    );
                    const isSelected = itemIndex === selectedIndex;
                    const isExpanded = expandedChunkId === chunk.id;
                    const relevancePercent = Math.min(100, Math.round(chunk.relevance_score * 100));

                    return (
                      <div
                        key={`chunk-${chunk.id}`}
                        className={`command-result-item code-chunk-item ${isSelected ? "selected" : ""}`}
                        onClick={() => handleSelect({ kind: "code_chunk", item: chunk })}
                        onMouseEnter={() => setSelectedIndex(itemIndex)}
                      >
                        <div className="result-icon-wrapper code-icon">
                          <Code2 size={16} />
                        </div>
                        <div className="result-info" style={{ minWidth: 0, width: "100%" }}>
                          <div className="result-primary-line">
                            <span className="code-file-path">{chunk.file_path}</span>
                            <span className="code-line-badge">
                              L{chunk.start_line}-L{chunk.end_line}
                            </span>
                            <span className="badge badge-label" style={{ fontSize: "0.65rem", padding: "1px 5px" }}>
                              {chunk.language}
                            </span>
                            <span className="badge badge-success" style={{ fontSize: "0.65rem", marginLeft: "auto" }}>
                              {relevancePercent}% match
                            </span>
                          </div>

                          <div className="result-secondary-line" style={{ marginTop: "0.35rem" }}>
                            <span className="repo-owner-tag">{chunk.repository_name}</span>
                            <button
                              type="button"
                              className="code-expand-toggle"
                              onClick={(e) => {
                                e.stopPropagation();
                                setExpandedChunkId(isExpanded ? null : chunk.id);
                              }}
                            >
                              {isExpanded ? "Collapse preview" : "View snippet"}
                            </button>
                          </div>

                          {/* Code Preview Block */}
                          <div className={`code-preview-block ${isExpanded ? "expanded" : "collapsed"}`}>
                            <pre>
                              <code>{chunk.content}</code>
                            </pre>
                          </div>
                        </div>

                        <div className="result-meta">
                          {isSelected && <CornerDownLeft size={13} className="enter-hint" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* 2. Past AI Investigations Category */}
              {results.investigations && results.investigations.length > 0 && (
                <div className="command-category-group">
                  <div className="command-category-header">
                    <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                      <Lightbulb size={13} color="#fbbf24" />
                      PREVIOUS AI INVESTIGATIONS
                    </span>
                    <span className="category-count">{results.investigations.length}</span>
                  </div>
                  {results.investigations.map((inv) => {
                    const itemIndex = flattenedItems.findIndex(
                      (i) => i.kind === "investigation" && i.item.id === inv.id
                    );
                    const isSelected = itemIndex === selectedIndex;

                    return (
                      <div
                        key={`inv-${inv.id}`}
                        className={`command-result-item investigation-item ${isSelected ? "selected" : ""}`}
                        onClick={() => handleSelect({ kind: "investigation", item: inv })}
                        onMouseEnter={() => setSelectedIndex(itemIndex)}
                      >
                        <div className="result-icon-wrapper inv-icon">
                          <Bot size={16} />
                        </div>
                        <div className="result-info">
                          <div className="result-primary-line">
                            <span className="issue-num-tag">#{inv.issue_number}</span>
                            <span className="result-title">
                              <HighlightText text={inv.issue_title} query={query} />
                            </span>
                            {inv.priority && (
                              <span
                                className={`badge ${
                                  inv.priority.includes("P0")
                                    ? "badge-danger"
                                    : inv.priority.includes("P1")
                                    ? "badge-warning"
                                    : "badge-label"
                                }`}
                                style={{ fontSize: "0.65rem", padding: "1px 6px" }}
                              >
                                {inv.priority}
                              </span>
                            )}
                          </div>

                          <div className="investigation-root-cause">
                            <span className="inv-badge-error">{inv.error_type}</span>
                            <span className="inv-hypothesis-text">
                              <HighlightText text={inv.root_cause_hypothesis} query={query} />
                            </span>
                          </div>

                          <div className="result-secondary-line" style={{ marginTop: "0.25rem" }}>
                            <span className="repo-owner-tag">{inv.repository_name}</span>
                            {inv.fix_target_file && (
                              <span className="inv-target-file">
                                Target: <code>{inv.fix_target_file}</code>
                              </span>
                            )}
                            {inv.confidence && (
                              <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginLeft: "auto" }}>
                                {(inv.confidence * 100).toFixed(0)}% confidence
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="result-meta">
                          {isSelected && <CornerDownLeft size={13} className="enter-hint" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* 3. Repositories Category */}
              {results.repositories.length > 0 && (
                <div className="command-category-group">
                  <div className="command-category-header">
                    <span>REPOSITORIES</span>
                    <span className="category-count">{results.repositories.length}</span>
                  </div>
                  {results.repositories.map((repo) => {
                    const itemIndex = flattenedItems.findIndex(
                      (i) => i.kind === "repository" && i.item.id === repo.id
                    );
                    const isSelected = itemIndex === selectedIndex;

                    return (
                      <div
                        key={`repo-${repo.id}`}
                        className={`command-result-item ${isSelected ? "selected" : ""}`}
                        onClick={() => handleSelect({ kind: "repository", item: repo })}
                        onMouseEnter={() => setSelectedIndex(itemIndex)}
                      >
                        <div className="result-icon-wrapper repo-icon">
                          <FolderGit2 size={16} />
                        </div>
                        <div className="result-info">
                          <div className="result-primary-line">
                            <span className="result-title">
                              <HighlightText text={repo.full_name} query={query} />
                            </span>
                            {repo.language && (
                              <span className="badge badge-label" style={{ fontSize: "0.65rem", padding: "1px 6px" }}>
                                {repo.language}
                              </span>
                            )}
                          </div>
                          {repo.description && (
                            <div className="result-secondary-line">
                              <HighlightText text={repo.description} query={query} />
                            </div>
                          )}
                        </div>
                        <div className="result-meta">
                          {repo.stargazers_count > 0 && (
                            <span className="result-stars" title={`${repo.stargazers_count} stars`}>
                              <Star size={12} fill="#eab308" color="#eab308" />
                              <span>{repo.stargazers_count}</span>
                            </span>
                          )}
                          {isSelected && <CornerDownLeft size={13} className="enter-hint" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* 4. Issues Category */}
              {results.issues.length > 0 && (
                <div className="command-category-group">
                  <div className="command-category-header">
                    <span>ISSUES</span>
                    <span className="category-count">{results.issues.length}</span>
                  </div>
                  {results.issues.map((issue) => {
                    const itemIndex = flattenedItems.findIndex(
                      (i) => i.kind === "issue" && i.item.id === issue.id
                    );
                    const isSelected = itemIndex === selectedIndex;

                    return (
                      <div
                        key={`issue-${issue.id}`}
                        className={`command-result-item ${isSelected ? "selected" : ""}`}
                        onClick={() => handleSelect({ kind: "issue", item: issue })}
                        onMouseEnter={() => setSelectedIndex(itemIndex)}
                      >
                        <div className="result-icon-wrapper issue-icon">
                          <CircleDot size={16} />
                        </div>
                        <div className="result-info">
                          <div className="result-primary-line">
                            <span className="issue-num-tag">#{issue.issue_number}</span>
                            <span className="result-title">
                              <HighlightText text={issue.title} query={query} />
                            </span>
                          </div>
                          <div className="result-secondary-line">
                            <span className="repo-owner-tag">{issue.repository_name}</span>
                            {issue.state === "open" ? (
                              <span className="badge badge-success" style={{ fontSize: "0.65rem", padding: "1px 5px" }}>
                                Open
                              </span>
                            ) : (
                              <span className="badge" style={{ fontSize: "0.65rem", padding: "1px 5px", backgroundColor: "rgba(100, 116, 139, 0.2)", color: "#94a3b8" }}>
                                Closed
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="result-meta">
                          {isSelected && <CornerDownLeft size={13} className="enter-hint" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* 5. Pull Requests Category */}
              {results.pull_requests.length > 0 && (
                <div className="command-category-group">
                  <div className="command-category-header">
                    <span>PULL REQUESTS</span>
                    <span className="category-count">{results.pull_requests.length}</span>
                  </div>
                  {results.pull_requests.map((pr) => {
                    const itemIndex = flattenedItems.findIndex(
                      (i) => i.kind === "pull_request" && i.item.id === pr.id
                    );
                    const isSelected = itemIndex === selectedIndex;

                    return (
                      <div
                        key={`pr-${pr.id}`}
                        className={`command-result-item ${isSelected ? "selected" : ""}`}
                        onClick={() => handleSelect({ kind: "pull_request", item: pr })}
                        onMouseEnter={() => setSelectedIndex(itemIndex)}
                      >
                        <div className="result-icon-wrapper pr-icon">
                          <GitPullRequest size={16} />
                        </div>
                        <div className="result-info">
                          <div className="result-primary-line">
                            <span className="pr-num-tag">#{pr.pr_number}</span>
                            <span className="result-title">
                              <HighlightText text={pr.title} query={query} />
                            </span>
                          </div>
                          <div className="result-secondary-line">
                            <span className="repo-owner-tag">{pr.repository_name}</span>
                            {pr.is_merged ? (
                              <span className="badge badge-label" style={{ fontSize: "0.65rem", padding: "1px 5px", backgroundColor: "rgba(168, 85, 247, 0.2)", color: "#c084fc" }}>
                                Merged
                              </span>
                            ) : pr.state === "open" ? (
                              <span className="badge badge-success" style={{ fontSize: "0.65rem", padding: "1px 5px" }}>
                                Open
                              </span>
                            ) : (
                              <span className="badge" style={{ fontSize: "0.65rem", padding: "1px 5px", backgroundColor: "rgba(100, 116, 139, 0.2)", color: "#94a3b8" }}>
                                Closed
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="result-meta">
                          {isSelected && <CornerDownLeft size={13} className="enter-hint" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Shortcut Bar */}
        <div className="command-palette-footer">
          <div className="footer-shortcuts">
            <span className="footer-shortcut">
              <kbd>Tab</kbd> Mode
            </span>
            <span className="footer-shortcut">
              <kbd>↑</kbd>
              <kbd>↓</kbd> Navigate
            </span>
            <span className="footer-shortcut">
              <kbd>↵</kbd> Select / Explain
            </span>
            <span className="footer-shortcut">
              <kbd>ESC</kbd> Close
            </span>
          </div>
          <div className="footer-branding">
            <Sparkles size={11} color="#818cf8" style={{ marginRight: "3px" }} />
            <span>RepoMind AI Intelligence</span>
          </div>
        </div>
      </div>
    </div>
  );
};
