import { useState } from "react";
import { NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { DashboardPage } from "@/pages/DashboardPage";
import { AuditTrailPage } from "@/pages/AuditTrailPage";
import { ResultsPage } from "@/pages/ResultsPage";
import { RecoveriesPage } from "@/pages/RecoveriesPage";
import { DecisionPage } from "@/pages/DecisionPage";
import { TransactionsPage } from "@/pages/TransactionsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { SimulatorPanel } from "@/components/SimulatorPanel";

const links = [
  { to: "/", label: "Overview", end: true },
  { to: "/recoveries", label: "Recoveries" },
  { to: "/transactions", label: "Transactions" },
  { to: "/decisions", label: "Decisions" },
  { to: "/audit", label: "Audit trail" },
  { to: "/results", label: "Evaluation" },
  { to: "/settings", label: "Settings" },
];

export function App() {
  const [isSimulatorOpen, setIsSimulatorOpen] = useState(false);
  const navigate = useNavigate();

  const handleSimulateSuccess = (transactionId: string) => {
    navigate("/", { state: { highlightId: transactionId }, replace: true });
  };

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
          {links.map((link, index) => (
            <NavLink
              key={`${link.label}-${index}`}
              to={link.to}
              end={link.end}
              className={({ isActive }) =>
                isActive ? "nav-link active" : "nav-link"
              }
            >
              {link.label}
            </NavLink>
          ))}
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
              onClick={() => setIsSimulatorOpen(true)}
              className="border-none bg-brand hover:bg-brand-light text-white font-semibold text-75 py-2 px-4 rounded-small cursor-pointer transition-colors"
            >
              Simulate payment failure
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
            <Route path="/recoveries" element={<RecoveriesPage />} />
            <Route path="/transactions" element={<TransactionsPage />} />
            <Route
              path="/decisions/:transactionId"
              element={<DecisionPage />}
            />
            <Route path="/decisions" element={<RecoveriesPage />} />
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
    </div>
  );
}
