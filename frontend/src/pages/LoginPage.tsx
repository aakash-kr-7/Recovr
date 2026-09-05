import React, { useState } from "react";
import { useMerchant } from "@/context/MerchantContext";
import { useTheme } from "@/context/useTheme";
import { useNavigate } from "react-router-dom";

export function LoginPage() {
  const { setMerchantName } = useMerchant();
  const { theme, toggleTheme } = useTheme();
  const [name, setName] = useState("Acme Retail Pvt Ltd");
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim()) {
      setMerchantName(name.trim());
      navigate("/", { replace: true });
    }
  };

  return (
    <div className="login-screen">
      <button
        onClick={toggleTheme}
        className="theme-toggle"
        style={{ position: "absolute", top: "24px", right: "24px" }}
        aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      >
        {theme === "dark" ? "Light theme" : "Dark theme"}
      </button>

      <div className="login-card">
        <div className="login-logo-wrap">
          <img src="/logo.svg" alt="RECOVR Logo" width="56" height="56" />
        </div>

        <div>
          <span className="login-eyebrow">AI Revenue Recovery Agent</span>
          <h1 className="login-title">Welcome to RECOVR</h1>
          <p className="login-subtitle">
            Autonomous payment failure triage and revenue recovery workspace.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div>
            <label htmlFor="merchantName" className="login-label">
              Operating as Merchant
            </label>
            <input
              id="merchantName"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Acme Retail Pvt Ltd"
              required
              className="login-input"
            />
            <div className="login-hint">
              Sets operator context and autonomous triage rules for this session.
            </div>
          </div>

          <button type="submit" className="login-submit-btn">
            Continue to workspace →
          </button>
        </form>

        <div className="login-footer-meta">
          <span className="status-dot" style={{ width: "6px", height: "6px" }} />
          <span>Test Environment · Provider-Safe Operations</span>
        </div>
      </div>
    </div>
  );
}
