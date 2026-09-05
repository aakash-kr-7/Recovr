import { useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { DashboardPage } from "@/pages/DashboardPage";
import { AuditTrailPage } from "@/pages/AuditTrailPage";
import { ResultsPage } from "@/pages/ResultsPage";
import { RecoveriesPage } from "@/pages/RecoveriesPage";
import { DecisionPage } from "@/pages/DecisionPage";
import { TransactionsPage } from "@/pages/TransactionsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { LiveModePage } from "@/pages/LiveModePage";
import { SimulatorPanel } from "@/components/SimulatorPanel";
import { GuidedTour } from "@/components/GuidedTour";
import { api } from "@/lib/api";
import { useTheme } from "@/context/useTheme";
import { useMerchant } from "@/context/MerchantContext";
import { LoginPage } from "@/pages/LoginPage";
import type { LiveModeStatus } from "@/types/api";

const links = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/live", label: "Live Mode" },
  { to: "/recoveries", label: "Recoveries" },
  { to: "/transactions", label: "Transactions" },
  { to: "/audit", label: "Audit trail" },
  { to: "/results", label: "Evaluation" },
  { to: "/settings", label: "About & Configuration" },
];

export function App() {
  const { theme, toggleTheme } = useTheme();
  const { merchantName } = useMerchant();
  const [isSimulatorOpen, setIsSimulatorOpen] = useState(false);
  const [isTourOpen, setIsTourOpen] = useState(false);
  const [liveMode, setLiveMode] = useState<LiveModeStatus | null>(null);
  const [liveModeError, setLiveModeError] = useState<string | null>(null);
  const [liveModeChanging, setLiveModeChanging] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    const refresh = async () => {
      try {
        const status = await api.getLiveModeStatus();
        if (!cancelled) {
          setLiveMode(status);
          setLiveModeError(null);
        }
      } catch (error) {
        if (!cancelled) {
          setLiveModeError(error instanceof Error ? error.message : "Live Mode unavailable");
        }
      }
    };
    void refresh();
    const poll = window.setInterval(refresh, liveMode?.is_running ? 1000 : 2000);
    return () => {
      cancelled = true;
      window.clearInterval(poll);
    };
  }, [liveMode?.is_running]);

  const handleSimulateSuccess = (transactionId: string) => {
    navigate("/", { state: { highlightId: transactionId }, replace: true });
  };

  const toggleLiveMode = async () => {
    setLiveModeChanging(true);
    setLiveModeError(null);
    try {
      if (liveMode?.is_running) {
        await api.stopLiveMode();
      } else {
        await api.startLiveMode();
        navigate("/live");
      }
      setLiveMode(await api.getLiveModeStatus());
    } catch (error) {
      setLiveModeError(error instanceof Error ? error.message : "Live Mode request failed");
    } finally {
      setLiveModeChanging(false);
    }
  };

  const getMerchantInitials = (name: string): string => {
    const parts = name.trim().split(/\s+/).filter(Boolean);
    if (parts.length === 0) return "OP";
    if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
    return (parts[0][0] + parts[1][0]).toUpperCase();
  };

  let liveStatusText = "";
  if (!liveMode || (liveMode.current_step === 0 && !liveMode.is_running)) {
    liveStatusText = "Live Mode: ready";
  } else if (liveMode.is_running) {
    liveStatusText = `Live Mode running — step ${Math.max(1, liveMode.current_step)} of ${liveMode.sequence_length}`;
  } else if (liveMode.current_step >= liveMode.sequence_length) {
    liveStatusText = `Live Mode complete — ${liveMode.sequence_length} scenarios run`;
  } else {
    liveStatusText = `Live Mode paused — step ${liveMode.current_step} of ${liveMode.sequence_length}`;
  }

  if (!merchantName) {
    return <LoginPage />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <img src="/logo.svg" alt="RECOVR" width="24" height="24" className="brand-logo" />
          <div>
            <strong>RECOVR</strong>
            <small>Revenue recovery</small>
          </div>
        </div>
        <nav aria-label="Primary navigation">
          {links.map((link, index) => {
            const isLive = link.to === "/live";
            return (
              <NavLink
                key={`${link.label}-${index}`}
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  isActive ? "nav-link active" : "nav-link"
                }
                style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
              >
                <span>{link.label}</span>
                {isLive && liveMode?.is_running && (
                  <span className="live-nav-badge is-live">
                    <span className="pulse-dot" />
                    LIVE
                  </span>
                )}
                {isLive && !liveMode?.is_running && (liveMode?.current_step ?? 0) > 0 && (
                  <span className="live-nav-badge is-complete">
                    Complete
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <span className="status-dot" /> Test environment
          <br />
          <small>Provider-safe operations</small>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <span className="merchant-label">Merchant workspace</span>
            <strong>{merchantName}</strong>
          </div>
          <div className="topbar-meta">
            <button
              onClick={toggleTheme}
              className="theme-toggle"
              aria-pressed={theme === "dark"}
              aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
            >
              {theme === "dark" ? "Light theme" : "Dark theme"}
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }} data-tour="simulation-controls">
              <div className="live-mode-control">
                <button
                  onClick={() => void toggleLiveMode()}
                  disabled={liveModeChanging}
                  className={liveMode?.is_running ? "live-mode-button is-running" : "live-mode-button"}
                  aria-label={liveMode?.is_running ? "Stop Live Mode" : "Start Live Mode"}
                >
                  {liveMode?.is_running ? "Stop Live Mode" : "Start Live Mode"}
                </button>
                <span className="live-mode-status" aria-live="polite">
                  {liveStatusText}
                </span>
                {liveModeError && <span className="live-mode-error">{liveModeError}</span>}
              </div>
              <button
                onClick={() => setIsSimulatorOpen(true)}
                className="border-none bg-brand hover:bg-brand-light text-white font-semibold text-75 py-2 px-4 rounded-small cursor-pointer transition-colors"
              >
                Simulate payment failure
              </button>
            </div>
            <button onClick={() => setIsTourOpen(true)} className="tour-button">
              Take a tour
            </button>
            <span
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xsmall bg-brand-subtle text-brand border border-brand/20 font-bold text-50 tracking-wider uppercase ml-2"
              title="Test mode: simulated and bounded recovery actions only"
            >
              <span className="w-1.5 h-1.5 rounded-round bg-brand inline-block" />
              TEST MODE
            </span>
            <div className="operator-profile-badge" title={`Active operator: ${merchantName}`}>
              <span className="avatar" aria-live="polite" aria-label={`Current operator: ${merchantName}`}>
                {getMerchantInitials(merchantName)}
              </span>
              <span className="operator-profile-name">{merchantName}</span>
            </div>
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/live" element={<LiveModePage />} />
            <Route path="/recoveries" element={<RecoveriesPage />} />
            <Route path="/transactions" element={<TransactionsPage />} />
            <Route
              path="/decisions/:transactionId"
              element={<DecisionPage />}
            />
            <Route path="/decisions" element={<Navigate to="/recoveries" replace />} />
            <Route path="/audit" element={<AuditTrailPage />} />
            <Route path="/results" element={<ResultsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>

      <SimulatorPanel
        isOpen={isSimulatorOpen}
        onClose={() => setIsSimulatorOpen(false)}
        onSuccess={handleSimulateSuccess}
      />
      <GuidedTour open={isTourOpen} onClose={() => setIsTourOpen(false)} />
    </div>
  );
}
