import { NavLink, Route, Routes } from "react-router-dom";
import { DashboardPage } from "@/pages/DashboardPage";
import { AuditTrailPage } from "@/pages/AuditTrailPage";
import { ResultsPage } from "@/pages/ResultsPage";
import { RecoveriesPage } from "@/pages/RecoveriesPage";
import { DecisionPage } from "@/pages/DecisionPage";
import { TransactionsPage } from "@/pages/TransactionsPage";

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
            <span className="badge badge-neutral">TEST MODE</span>
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
            <Route
              path="/settings"
              element={
                <div className="page-stack">
                  <div className="state">
                    Settings are not exposed by the current backend contract.
                  </div>
                </div>
              }
            />
          </Routes>
        </main>
      </div>
    </div>
  );
}
