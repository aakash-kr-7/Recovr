import { useMemo, useState } from "react";
import { ActivityTable } from "@/components/ActivityTable";
import { PageHeader } from "@/components/PageHeader";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";
import type { TriageAction } from "@/types/api";
import { PageContext } from "@/components/PageContext";

export function RecoveriesPage() {
  const { transactions, loading, error } = useRecentTransactions(200);
  const [action, setAction] = useState<TriageAction | "all">("all");
  const [path, setPath] = useState<"all" | "deterministic" | "reasoning">(
    "all",
  );
  const [mode, setMode] = useState<"all" | "real" | "simulated">("all");
  const filtered = useMemo(
    () =>
      transactions.filter(
        (item) =>
          (action === "all" || item.action === action) &&
          (path === "all" || item.path_taken === path) &&
          (mode === "all" ||
            (mode === "real"
              ? item.recovery_outcome?.mode === "REAL_RAZORPAY_ACTION"
              : item.is_synthetic ||
                item.recovery_outcome?.mode === "BOUNDED_SIMULATION")),
      ),
    [transactions, action, path, mode],
  );
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="OPERATIONAL WORKLIST · OPEN & ACTIONABLE CASES"
        title="Recoveries"
        description="Prioritize open and actionable recovery cases. Filter by action, decision path, or execution mode — click any row to inspect its full decision lifecycle."
      />
      <div className="filter-bar">
        <label>
          Action
          <select
            value={action}
            onChange={(e) => setAction(e.target.value as TriageAction | "all")}
          >
            <option value="all">All actions</option>
            <option value="retry_same_rail">Retry</option>
            <option value="retry_alt_rail">Alternate rail</option>
            <option value="escalate_to_dunning">Dunning</option>
            <option value="hold_for_review">Review</option>
            <option value="no_action">No action</option>
          </select>
        </label>
        <label>
          Decision path
          <select
            value={path}
            onChange={(e) =>
              setPath(e.target.value as "all" | "deterministic" | "reasoning")
            }
          >
            <option value="all">All paths</option>
            <option value="deterministic">Deterministic</option>
            <option value="reasoning">Reasoning</option>
          </select>
        </label>
        <label>
          Execution
          <select
            value={mode}
            onChange={(e) =>
              setMode(e.target.value as "all" | "real" | "simulated")
            }
          >
            <option value="all">Real + simulated</option>
            <option value="real">Real Razorpay</option>
            <option value="simulated">Simulated</option>
          </select>
        </label>
      </div>
      {loading && !transactions.length ? (
        <div className="state">Loading recoveries…</div>
      ) : error ? (
        <div className="state state-error">{error}</div>
      ) : !filtered.length ? (
        <div className="state">No recoveries match these filters.</div>
      ) : (
        <section className="panel" data-tour="recoveries-table">
          <ActivityTable transactions={filtered} />
        </section>
      )}

      <PageContext>
        These are the cases still awaiting resolution. You can click any row to see exactly why the system chose that action, and trace the decision path from failure to execution.
      </PageContext>
    </div>
  );
}
