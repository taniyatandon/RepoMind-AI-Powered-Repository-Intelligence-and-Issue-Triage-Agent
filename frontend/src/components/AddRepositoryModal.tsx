import React, { useEffect, useRef, useState } from "react";
import { apiAddRepository, apiGetJobStatus } from "../api";
import { IngestionJob } from "../types";
import {
  AlertCircle,
  ArrowRight,
  Check,
  CheckCircle2,
  Clock,
  Database,
  FolderGit2,
  GitBranch,
  Loader2,
  Sparkles,
  X,
} from "lucide-react";

interface AddRepositoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const AddRepositoryModal: React.FC<AddRepositoryModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [repoInput, setRepoInput] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [activeJob, setActiveJob] = useState<IngestionJob | null>(null);
  const pollTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, []);

  if (!isOpen) return null;

  const startPolling = (jobId: number) => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);

    pollTimerRef.current = window.setInterval(async () => {
      try {
        const job = await apiGetJobStatus(jobId);
        setActiveJob(job);

        if (job.status === "completed") {
          if (pollTimerRef.current) clearInterval(pollTimerRef.current);
          setIsSubmitting(false);
          // Let user see completed state briefly before closing
          setTimeout(() => {
            onSuccess();
            handleClose();
          }, 1400);
        } else if (job.status === "failed") {
          if (pollTimerRef.current) clearInterval(pollTimerRef.current);
          setIsSubmitting(false);
          setError(job.error_message || "Ingestion failed unexpectedly.");
        }
      } catch (err: any) {
        console.error("Polling error:", err);
      }
    }, 1500);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repoInput.trim()) return;

    setError(null);
    setIsSubmitting(true);
    setActiveJob(null);

    try {
      const res = await apiAddRepository(repoInput.trim());
      setActiveJob({
        id: res.job_id,
        repository_id: null,
        repository_name: res.repository_name,
        status: "pending",
        total_issues_ingested: 0,
        started_at: new Date().toISOString(),
        completed_at: null,
        error_message: null,
      });
      startPolling(res.job_id);
    } catch (err: any) {
      setError(err.message || "Failed to initiate repository ingestion.");
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    setRepoInput("");
    setError(null);
    setIsSubmitting(false);
    setActiveJob(null);
    onClose();
  };

  const selectExample = (example: string) => {
    setRepoInput(example);
    setError(null);
  };

  const getStepState = (stepNumber: number) => {
    if (!activeJob) return "idle";
    if (activeJob.status === "failed") return "failed";
    if (activeJob.status === "completed") return "done";

    if (activeJob.status === "pending") {
      return stepNumber === 1 ? "active" : "pending";
    }
    if (activeJob.status === "running") {
      if (stepNumber <= 2) return "done";
      if (stepNumber === 3) return "active";
      return "pending";
    }
    return "idle";
  };

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: "540px", padding: "1.75rem" }}
      >
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: "flex", alignItems: "center", gap: "0.6rem" }}>
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "var(--radius-sm)",
                backgroundColor: "rgba(99, 102, 241, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#818cf8",
              }}
            >
              <FolderGit2 size={18} />
            </div>
            <div>
              <h2 className="modal-title" style={{ fontSize: "1.2rem" }}>Ingest GitHub Repository</h2>
              <span style={{ fontSize: "0.775rem", color: "var(--text-muted)" }}>
                Asynchronous background ingestion with duplicate-safe upsert
              </span>
            </div>
          </div>
          <button
            className="close-btn"
            onClick={handleClose}
            disabled={isSubmitting && activeJob?.status === "running"}
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {error && (
          <div className="alert alert-danger">
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: "2px" }} />
            <div style={{ fontSize: "0.825rem" }}>{error}</div>
          </div>
        )}

        {/* Live Multi-Stage Ingestion Pipeline Visualizer */}
        {activeJob && (
          <div
            style={{
              padding: "1rem",
              borderRadius: "var(--radius-md)",
              backgroundColor: "var(--bg-card)",
              border: "1px solid var(--border-color)",
              marginBottom: "1.5rem",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.875rem" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: "0.75rem",
                    color: "var(--text-muted)",
                  }}
                >
                  Job #{activeJob.id}
                </span>
                <span style={{ color: "var(--border-color)" }}>•</span>
                <strong style={{ fontSize: "0.85rem", color: "var(--text-primary)" }}>
                  {activeJob.repository_name}
                </strong>
              </div>

              <span
                className={`badge ${
                  activeJob.status === "completed"
                    ? "badge-open"
                    : activeJob.status === "failed"
                    ? "badge-closed"
                    : "badge-label"
                }`}
                style={{ textTransform: "uppercase", fontSize: "0.7rem" }}
              >
                {activeJob.status === "running" && (
                  <Loader2 size={10} style={{ animation: "spin 1s linear infinite" }} />
                )}
                {activeJob.status}
              </span>
            </div>

            {/* Stepped Progress Indicator */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, 1fr)",
                gap: "0.5rem",
                marginTop: "0.5rem",
                fontSize: "0.725rem",
              }}
            >
              <div
                style={{
                  padding: "0.5rem",
                  borderRadius: "var(--radius-xs)",
                  backgroundColor:
                    getStepState(1) === "done"
                      ? "rgba(16, 185, 129, 0.12)"
                      : "rgba(255, 255, 255, 0.03)",
                  border: `1px solid ${
                    getStepState(1) === "done"
                      ? "rgba(16, 185, 129, 0.3)"
                      : "var(--border-subtle)"
                  }`,
                  color: getStepState(1) === "done" ? "#34d399" : "var(--text-secondary)",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.35rem",
                }}
              >
                {getStepState(1) === "done" ? <Check size={12} /> : <Clock size={12} />}
                <span>1. Job Queued</span>
              </div>

              <div
                style={{
                  padding: "0.5rem",
                  borderRadius: "var(--radius-xs)",
                  backgroundColor:
                    activeJob.status === "running"
                      ? "rgba(99, 102, 241, 0.15)"
                      : activeJob.status === "completed"
                      ? "rgba(16, 185, 129, 0.12)"
                      : "rgba(255, 255, 255, 0.03)",
                  border: `1px solid ${
                    activeJob.status === "running"
                      ? "rgba(99, 102, 241, 0.4)"
                      : activeJob.status === "completed"
                      ? "rgba(16, 185, 129, 0.3)"
                      : "var(--border-subtle)"
                  }`,
                  color:
                    activeJob.status === "running"
                      ? "#a5b4fc"
                      : activeJob.status === "completed"
                      ? "#34d399"
                      : "var(--text-secondary)",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.35rem",
                }}
              >
                {activeJob.status === "running" ? (
                  <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />
                ) : activeJob.status === "completed" ? (
                  <Check size={12} />
                ) : (
                  <Database size={12} />
                )}
                <span>2. Ingesting</span>
              </div>

              <div
                style={{
                  padding: "0.5rem",
                  borderRadius: "var(--radius-xs)",
                  backgroundColor:
                    activeJob.status === "completed"
                      ? "rgba(16, 185, 129, 0.12)"
                      : "rgba(255, 255, 255, 0.03)",
                  border: `1px solid ${
                    activeJob.status === "completed"
                      ? "rgba(16, 185, 129, 0.3)"
                      : "var(--border-subtle)"
                  }`,
                  color:
                    activeJob.status === "completed"
                      ? "#34d399"
                      : "var(--text-secondary)",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.35rem",
                }}
              >
                {activeJob.status === "completed" ? (
                  <CheckCircle2 size={12} />
                ) : (
                  <Sparkles size={12} />
                )}
                <span>3. Ready</span>
              </div>
            </div>

            {/* Live Message */}
            <div
              style={{
                marginTop: "0.75rem",
                fontSize: "0.8rem",
                color: "var(--text-secondary)",
                display: "flex",
                alignItems: "center",
                gap: "0.5rem",
              }}
            >
              {activeJob.status === "pending" && (
                <span>Background worker picking up ingestion task...</span>
              )}
              {activeJob.status === "running" && (
                <span>Fetching metadata & paginating issues from GitHub REST API...</span>
              )}
              {activeJob.status === "completed" && (
                <span style={{ color: "#34d399", fontWeight: 600 }}>
                  Ingestion complete! Stored {activeJob.total_issues_ingested} issues.
                </span>
              )}
              {activeJob.status === "failed" && (
                <span style={{ color: "#f87171" }}>
                  Failed: {activeJob.error_message}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Input Form */}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Repository Identifier or URL</label>
            <div style={{ position: "relative" }}>
              <input
                type="text"
                required
                className="form-input"
                style={{ paddingLeft: "2.35rem" }}
                placeholder="e.g. pallets/flask or https://github.com/pallets/flask"
                value={repoInput}
                disabled={isSubmitting}
                onChange={(e) => setRepoInput(e.target.value)}
              />
              <GitBranch
                size={15}
                style={{
                  position: "absolute",
                  left: "0.85rem",
                  top: "50%",
                  transform: "translateY(-50%)",
                  color: "var(--text-muted)",
                }}
              />
            </div>
            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.35rem" }}>
              Accepts <code>owner/repo</code> format or complete GitHub repository URLs.
            </p>
          </div>

          {/* Quick Examples */}
          <div style={{ marginBottom: "1.5rem" }}>
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", display: "block", marginBottom: "0.4rem" }}>
              Or try a popular open-source project:
            </span>
            <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
              {["pallets/flask", "psf/requests", "tiangolo/fastapi"].map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => selectExample(ex)}
                  disabled={isSubmitting}
                  style={{
                    fontSize: "0.75rem",
                    padding: "3px 8px",
                    background: "rgba(255, 255, 255, 0.04)",
                    border: "1px solid var(--border-color)",
                    borderRadius: "4px",
                    color: "var(--text-secondary)",
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.3rem",
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
                >
                  <FolderGit2 size={11} />
                  <span>{ex}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Footer Actions */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.75rem", paddingTop: "0.5rem" }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={handleClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={isSubmitting || !repoInput.trim()}
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={15} style={{ animation: "spin 1s linear infinite" }} />
                  <span>Ingesting Repository...</span>
                </>
              ) : (
                <>
                  <span>Start Ingestion</span>
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
