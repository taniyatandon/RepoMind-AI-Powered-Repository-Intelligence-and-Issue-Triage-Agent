import React, { useState } from "react";
import { apiLogin, apiRegister } from "../api";
import { User } from "../types";
import {
  AlertCircle,
  ArrowRight,
  Lock,
  Mail,
  Shield,
  User as UserIcon,
  X,
} from "lucide-react";

interface AuthModalProps {
  initialMode: "login" | "register";
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (user: User) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({
  initialMode,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [mode, setMode] = useState<"login" | "register">(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === "login") {
        const res = await apiLogin(email.trim(), password);
        onSuccess(res.user);
        onClose();
      } else {
        await apiRegister(email.trim(), password, username.trim() || undefined);
        // Automatically log in after registration
        const res = await apiLogin(email.trim(), password);
        onSuccess(res.user);
        onClose();
      }
    } catch (err: any) {
      setError(err.message || "An authentication error occurred.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-content"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: "440px", padding: "2rem" }}
      >
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "1.5rem" }}>
          <div>
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                fontSize: "0.75rem",
                color: "#a5b4fc",
                backgroundColor: "rgba(99, 102, 241, 0.12)",
                padding: "3px 8px",
                borderRadius: "var(--radius-full)",
                border: "1px solid rgba(99, 102, 241, 0.25)",
                marginBottom: "0.75rem",
                fontWeight: 600,
              }}
            >
              <Shield size={12} />
              <span>Argon2 & JWT Security</span>
            </div>
            <h2 style={{ fontSize: "1.375rem", fontWeight: 800, letterSpacing: "-0.025em" }}>
              {mode === "login" ? "Welcome back" : "Create developer account"}
            </h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.25rem" }}>
              {mode === "login"
                ? "Sign in to manage repositories and AI triage."
                : "Get started with full GitHub repo analysis & diffs."}
            </p>
          </div>
          <button className="close-btn" onClick={onClose} aria-label="Close dialog">
            <X size={18} />
          </button>
        </div>

        {/* Tab Toggle */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "0.25rem",
            backgroundColor: "rgba(255, 255, 255, 0.04)",
            padding: "3px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-subtle)",
            marginBottom: "1.25rem",
          }}
        >
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setError(null);
            }}
            style={{
              padding: "0.45rem",
              fontSize: "0.825rem",
              fontWeight: mode === "login" ? 600 : 500,
              color: mode === "login" ? "#ffffff" : "var(--text-secondary)",
              backgroundColor: mode === "login" ? "var(--bg-elevated)" : "transparent",
              border: mode === "login" ? "1px solid var(--border-color)" : "none",
              borderRadius: "4px",
              cursor: "pointer",
              transition: "all var(--transition-fast)",
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("register");
              setError(null);
            }}
            style={{
              padding: "0.45rem",
              fontSize: "0.825rem",
              fontWeight: mode === "register" ? 600 : 500,
              color: mode === "register" ? "#ffffff" : "var(--text-secondary)",
              backgroundColor: mode === "register" ? "var(--bg-elevated)" : "transparent",
              border: mode === "register" ? "1px solid var(--border-color)" : "none",
              borderRadius: "4px",
              cursor: "pointer",
              transition: "all var(--transition-fast)",
            }}
          >
            Register
          </button>
        </div>

        {error && (
          <div className="alert alert-danger" style={{ marginBottom: "1.25rem" }}>
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: "2px" }} />
            <div style={{ fontSize: "0.825rem" }}>{error}</div>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {mode === "register" && (
            <div className="form-group">
              <label className="form-label">Username (optional)</label>
              <div style={{ position: "relative" }}>
                <input
                  type="text"
                  className="form-input"
                  style={{ paddingLeft: "2.35rem" }}
                  placeholder="e.g. alexdev"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                />
                <UserIcon
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
            </div>
          )}

          <div className="form-group">
            <label className="form-label">Email Address</label>
            <div style={{ position: "relative" }}>
              <input
                type="email"
                required
                className="form-input"
                style={{ paddingLeft: "2.35rem" }}
                placeholder="developer@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <Mail
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
          </div>

          <div className="form-group">
            <label className="form-label">Password</label>
            <div style={{ position: "relative" }}>
              <input
                type="password"
                required
                minLength={6}
                className="form-input"
                style={{ paddingLeft: "2.35rem" }}
                placeholder="At least 6 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <Lock
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
          </div>

          <button
            type="submit"
            className="btn btn-primary"
            style={{ width: "100%", marginTop: "0.75rem", padding: "0.65rem 1rem" }}
            disabled={loading}
          >
            {loading ? (
              <div className="spinner spinner-sm" />
            ) : (
              <>
                <span>{mode === "login" ? "Sign In" : "Create Account"}</span>
                <ArrowRight size={15} />
              </>
            )}
          </button>
        </form>

        <div
          style={{
            marginTop: "1.25rem",
            paddingTop: "1rem",
            borderTop: "1px solid var(--border-subtle)",
            textAlign: "center",
            fontSize: "0.775rem",
            color: "var(--text-muted)",
          }}
        >
          <span>Demo credentials ready. Create any user or sign into existing account.</span>
        </div>
      </div>
    </div>
  );
};
