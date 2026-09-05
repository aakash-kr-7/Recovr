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
import type { LiveModeStatus } from "@/types/api";

const links = [
  { to: "/", label: "Overview", end: true },
  { to: "/live", label: "Live Mode" },
  { to: "/recoveries", label: "Recoveries" },
  { to: "/transactions", label: "Transactions" },
  { to: "/audit", label: "Audit trail" },
  { to: "/results", label: "Evaluation" },
  { to: "/settings", label: "About & Configuration" },
];

export function App() {
  const { theme, toggleTheme } = useTheme();
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

  const liveProgress = liveMode?.sequence_length
    ? `${Math.max(1, liveMode.current_step)} of ${liveMode.sequence_length}`
    : "Ready";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">R</span>
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
                    {liveMode?.current_step}/10
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
            <strong>RECOVR Operations</strong>
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
                  {liveMode?.is_running ? `LIVE · Step ${liveProgress}` : `Live Mode · ${liveProgress}`}
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
            <span className="avatar" aria-label="Current operator">
              OP
            </span>
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
