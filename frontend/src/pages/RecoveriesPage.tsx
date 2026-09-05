import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/PageHeader";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";
import { OutcomeBadge, StatusBadge } from "@/components/StatusBadges";
import { ACTION_LABELS, money } from "@/lib/operations";
import type { RecentTransaction, TriageAction } from "@/types/api";
import { PageContext } from "@/components/PageContext";

type StatusTab = "all" | "pending" | "recovered" | "failed" | "held";

function getStatusCategory(item: RecentTransaction): StatusTab {
  const status = item.recovery_outcome?.execution_status?.toUpperCase();
  if (!status || status === "PENDING") return "pending";
  if (status === "HELD" || status === "SKIPPED") return "held";
  if (status === "FAILED" || status === "FAILED_TO_EXECUTE") return "failed";
  if (status === "SIMULATED") {
    if (item.recovery_outcome?.observed_success) return "recovered";
    if (item.recovery_outcome?.observed_success === false) return "failed";
    return "pending";
  }
  if (
    item.recovery_outcome?.actual_recovered_inr !== null &&
    item.recovery_outcome?.actual_recovered_inr !== undefined &&
    item.recovery_outcome.actual_recovered_inr > 0
  )
    return "recovered";
  if (item.recovery_outcome?.observed_success === false) return "failed";
  return "pending";
}

export function RecoveriesPage() {
  const navigate = useNavigate();
  const { transactions, loading, error } = useRecentTransactions(200);
  const [statusTab, setStatusTab] = useState<StatusTab>("all");
  const [actionFilter, setActionFilter] = useState<TriageAction | "all">("all");

  /* Counts by status */
  const counts = useMemo(() => {
    const c = { all: 0, pending: 0, recovered: 0, failed: 0, held: 0 };
    for (const tx of transactions) {
      c.all++;
      c[getStatusCategory(tx)]++;
    }
    return c;
  }, [transactions]);

  /* Summary metrics */
  const metrics = useMemo(() => {
    let atRisk = 0;
    let recovered = 0;
    let pendingVolume = 0;
    for (const tx of transactions) {
      atRisk += tx.amount_inr;
      const actual = tx.recovery_outcome?.actual_recovered_inr ?? 0;
      recovered += actual;
      if (getStatusCategory(tx) === "pending") pendingVolume += tx.amount_inr;
    }
    return { atRisk, recovered, pendingVolume };
  }, [transactions]);

  /* Filter */
  const filtered = useMemo(
    () =>
      transactions.filter(
        (item) =>
          (statusTab === "all" || getStatusCategory(item) === statusTab) &&
          (actionFilter === "all" || item.action === actionFilter),
      ),
    [transactions, statusTab, actionFilter],
  );

  const statusTabs: { key: StatusTab; label: string; color: string }[] = [
    { key: "all", label: "All cases", color: "" },
    { key: "pending", label: "Pending", color: "var(--chart-notice, #9a6b25)" },
    {
      key: "recovered",
      label: "Recovered",
      color: "var(--chart-positive, #13825f)",
    },
    { key: "failed", label: "Failed", color: "#ad334d" },
    { key: "held", label: "Held for review", color: "#687589" },
  ];

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="OPERATIONAL WORKLIST"
        title="Recoveries"
        description="Your active work queue. Track every failed payment's recovery status — what happened, what's pending, and what needs attention."
      />

      {/* ── Summary KPI strip ── */}
      <div className="recoveries-kpi-strip">
        <div className="recoveries-kpi">
          <span className="recoveries-kpi-label">Total cases</span>
          <strong className="recoveries-kpi-value">{counts.all}</strong>
        </div>
        <div className="recoveries-kpi">
          <span className="recoveries-kpi-label">Revenue at risk</span>
          <strong className="recoveries-kpi-value">
            {money(metrics.atRisk)}
          </strong>
        </div>
        <div className="recoveries-kpi">
          <span className="recoveries-kpi-label">Recovered</span>
          <strong className="recoveries-kpi-value positive-text">
            {money(metrics.recovered)}
          </strong>
        </div>
        <div className="recoveries-kpi">
          <span className="recoveries-kpi-label">Pending volume</span>
          <strong className="recoveries-kpi-value">
            {money(metrics.pendingVolume)}
          </strong>
        </div>
      </div>

      {/* ── Status tabs ── */}
      <div className="recoveries-tabs-bar">
        <div className="recoveries-tabs" role="tablist" aria-label="Filter by status">
          {statusTabs.map((tab) => (
            <button
              key={tab.key}
              role="tab"
              aria-selected={statusTab === tab.key}
              className={`recoveries-tab ${statusTab === tab.key ? "active" : ""}`}
              onClick={() => setStatusTab(tab.key)}
            >
              <span
                className="recoveries-tab-dot"
                style={{
                  background:
                    tab.color || "var(--brand-primary, #3158c8)",
                }}
              />
              {tab.label}
              <span className="recoveries-tab-count">{counts[tab.key]}</span>
            </button>
          ))}
        </div>
        <div className="filter-bar" style={{ marginLeft: "auto" }}>
          <label>
            Action
            <select
              value={actionFilter}
              onChange={(e) =>
                setActionFilter(e.target.value as TriageAction | "all")
              }
            >
              <option value="all">All actions</option>
              <option value="retry_same_rail">Retry</option>
              <option value="retry_alt_rail">Alternate rail</option>
              <option value="escalate_to_dunning">Dunning</option>
              <option value="hold_for_review">Review</option>
              <option value="no_action">No action</option>
            </select>
          </label>
        </div>
      </div>

      {/* ── Table ── */}
      {loading && !transactions.length ? (
        <div className="state">Loading recoveries…</div>
      ) : error ? (
        <div className="state state-error">{error}</div>
      ) : !filtered.length ? (
        <div className="state">No recoveries match these filters.</div>
      ) : (
        <section className="panel" data-tour="recoveries-table">
          <div className="table-scroll">
            <table className="operations-table">
              <thead>
                <tr>
                  <th>Payment</th>
                  <th>Amount</th>
                  <th>Failure reason</th>
                  <th>Recommended action</th>
                  <th>Execution</th>
                  <th>Expected net</th>
                  <th>Outcome</th>
                  <th>Updated</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => {
                  const cat = getStatusCategory(item);
                  return (
                    <tr
                      key={item.transaction_id}
                      className={`clickable-row recoveries-row recoveries-row--${cat}`}
                      onClick={(e) => {
                        if ((e.target as HTMLElement).closest("a, button")) return;
                        navigate(`/decisions/${item.transaction_id}`);
                      }}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          navigate(`/decisions/${item.transaction_id}`);
                        }
                      }}
                      title="Click to view decision detail"
                    >
                      <td>
                        <Link
                          className="table-link"
                          to={`/decisions/${item.transaction_id}`}
                        >
                          {item.transaction_id.slice(0, 12)}…
                        </Link>
                        {item.is_synthetic && (
                          <span className="demo-label">DEMO DATA</span>
                        )}
                      </td>
                      <td style={{ fontWeight: 600 }}>
                        {money(item.amount_inr)}
                      </td>
                      <td>{item.decline_reason}</td>
                      <td>
                        <span className="recoveries-action-chip">
                          {ACTION_LABELS[item.action]}
                        </span>
                      </td>
                      <td>
                        <StatusBadge
                          outcome={item.recovery_outcome}
                          synthetic={item.is_synthetic}
                        />
                      </td>
                      <td>{money(item.selected_expected_net_recovery_inr)}</td>
                      <td>
                        <OutcomeBadge outcome={item.recovery_outcome} />
                      </td>
                      <td>
                        {new Date(item.created_at).toLocaleString()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <PageContext>
        This is your operational worklist — every failed payment that flowed
        through RECOVR. Use the status tabs to zero in on what needs attention.
        Click any row to see the full decision breakdown for that case.
      </PageContext>
    </div>
  );
}
