import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";
import { ACTION_LABELS, money } from "@/lib/operations";
import type { TriageAction } from "@/types/api";
import { PageHeader } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { ActivityTable } from "@/components/ActivityTable";

const actions: TriageAction[] = [
  "retry_same_rail",
  "retry_alt_rail",
  "escalate_to_dunning",
  "hold_for_review",
  "no_action",
];

export function DashboardPage() {
  const { transactions, loading, error } = useRecentTransactions();
  const atRisk = transactions.reduce(
    (total, item) => total + item.amount_inr,
    0,
  );
  const recovered = transactions.reduce(
    (total, item) => total + (item.recovery_outcome?.actual_recovered_inr ?? 0),
    0,
  );
  const expected = transactions.reduce(
    (total, item) => total + (item.selected_expected_net_recovery_inr ?? 0),
    0,
  );
  const pending = transactions.filter(
    (item) =>
      !item.recovery_outcome ||
      item.recovery_outcome.execution_status === "PENDING",
  ).length;
  const breakdown = actions.map((action) => ({
    action: ACTION_LABELS[action],
    count: transactions.filter((item) => item.action === action).length,
  }));

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="REVENUE RECOVERY OPERATIONS"
        title="Overview"
        description="Monitor failed payments, RECOVR decisions and recovery outcomes in one operating view."
      >
        <Link to="/recoveries" className="primary-button">
          View active recoveries
        </Link>
      </PageHeader>
      {error && (
        <div className="state state-error">
          The operations API is unavailable. {error}
        </div>
      )}
      {loading && transactions.length === 0 ? (
        <div className="state">Loading payment operations…</div>
      ) : transactions.length === 0 ? (
        <div className="state">
          No recovery activity yet. Incoming failed payments will appear here
          after triage.
        </div>
      ) : (
        <>
          <div className="kpi-grid">
            <KpiCard
              label="Revenue at risk"
              value={money(atRisk)}
              detail="Failed payments in this view"
            />
            <KpiCard
              label="Revenue recovered"
              value={money(recovered)}
              detail="Measured outcome only"
              positive
            />
            <KpiCard
              label="Incremental recovery"
              value="Unavailable"
              detail="Requires a comparable live baseline"
            />
            <KpiCard
              label="Recovery rate"
              value={
                atRisk
                  ? `${((recovered / atRisk) * 100).toFixed(1)}%`
                  : "Unavailable"
              }
              detail="Measured recovered ÷ at risk"
            />
            <KpiCard
              label="Expected recovery"
              value={money(expected)}
              detail="Expected net; not actual revenue"
            />
            <KpiCard
              label="Open recoveries"
              value={String(pending)}
              detail="Pending outcome or execution"
            />
          </div>
          <div className="content-grid content-grid-wide">
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Recovery performance</h2>
                  <p>Expected net recovery by selected action.</p>
                </div>
                <span className="badge badge-sim">LIVE VIEW</span>
              </div>
              <div className="chart-wrap">
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={breakdown}>
                    <XAxis dataKey="action" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar
                      dataKey="count"
                      name="Decisions"
                      fill="#3158c8"
                      radius={[2, 2, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </section>
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Recovery health</h2>
                  <p>Selected action mix</p>
                </div>
              </div>
              <div className="health-list">
                {breakdown.map((row) => (
                  <div key={row.action}>
                    <span>{row.action}</span>
                    <strong>{row.count}</strong>
                  </div>
                ))}
              </div>
            </section>
          </div>
          <section className="panel">
            <div className="panel-heading">
              <div>
                <h2>Recent recovery activity</h2>
                <p>Latest payment failures and their lifecycle.</p>
              </div>
              <Link to="/audit" className="text-link">
                Open audit trail
              </Link>
            </div>
            <ActivityTable transactions={transactions.slice(0, 8)} />
          </section>
        </>
      )}
    </div>
  );
}

