import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";
import { OutcomeBadge, StatusBadge } from "@/components/StatusBadges";
import { ACTION_LABELS, money, percent } from "@/lib/operations";
import type { TriageAction } from "@/types/api";
import { PageHeader } from "@/components/PageHeader";
import { PageContext } from "@/components/PageContext";

export function AuditTrailPage() {
  const { transactions, loading, error } = useRecentTransactions(200);
  const [action, setAction] = useState<TriageAction | "all">("all");
  const [path, setPath] = useState<"all" | "deterministic" | "reasoning">(
    "all",
  );
  const rows = useMemo(
    () =>
      transactions.filter(
        (item) =>
          (action === "all" || item.action === action) &&
          (path === "all" || item.path_taken === path),
      ),
    [transactions, action, path],
  );
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="TRACEABILITY LOG"
        title="Audit trail"
        description="Every triage decision, economic ranking and execution outcome retained for review."
      />
      <div className="filter-bar" data-tour="audit-filters">
        <label>
          Action
          <select
            value={action}
            onChange={(event) =>
              setAction(event.target.value as TriageAction | "all")
            }
          >
            <option value="all">All actions</option>
            <option value="retry_same_rail">Retry</option>
            <option value="retry_alt_rail">Alternate rail</option>
            <option value="hold_for_review">Review</option>
            <option value="escalate_to_dunning">Dunning</option>
            <option value="no_action">No action</option>
          </select>
        </label>
        <label>
          Decision path
          <select
            value={path}
            onChange={(event) =>
              setPath(
                event.target.value as "all" | "deterministic" | "reasoning",
              )
            }
          >
            <option value="all">All paths</option>
            <option value="deterministic">Deterministic</option>
            <option value="reasoning">Reasoning</option>
          </select>
        </label>
      </div>
      {loading && !transactions.length ? (
        <div className="state">Loading audit trail…</div>
      ) : error ? (
        <div className="state state-error">{error}</div>
      ) : !rows.length ? (
        <div className="state">No audit events match these filters.</div>
      ) : (
        <section className="panel table-scroll">
          <table className="operations-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Transaction</th>
                <th>Event</th>
                <th>Action</th>
                <th>Confidence</th>
                <th>Expected net</th>
                <th>Execution mode</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((item) => (
                <tr key={item.transaction_id}>
                  <td>{new Date(item.created_at).toLocaleString()}</td>
                  <td>
                    <Link
                      className="table-link"
                      to={`/decisions/${item.transaction_id}`}
                    >
                      {item.transaction_id.slice(0, 14)}…
                    </Link>
                  </td>
                  <td>
                    {item.path_taken === "reasoning"
                      ? "AI-informed decision"
                      : "Deterministic decision"}
                  </td>
                  <td>{ACTION_LABELS[item.action]}</td>
                  <td>{percent(item.confidence)}</td>
                  <td>{money(item.selected_expected_net_recovery_inr)}</td>
                  <td>
                    <StatusBadge
                      outcome={item.recovery_outcome}
                      synthetic={item.is_synthetic}
                    />
                  </td>
                  <td>
                    <OutcomeBadge outcome={item.recovery_outcome} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <PageContext>
        This shows HOW each decision was reasoned, not just what happened. Confidence scores only appear for AI-informed decisions — deterministic decisions don't need a confidence score because the rule is fixed.
      </PageContext>
    </div>
  );
}
