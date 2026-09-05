import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  chartAxis,
  chartCursor,
  chartGrid,
  chartTick,
  chartTooltipItemStyle,
  chartTooltipLabelStyle,
  chartTooltipStyle,
} from "@/lib/chartTheme";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";
import { ACTION_LABELS, money } from "@/lib/operations";
import type { TriageAction } from "@/types/api";
import { PageHeader } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { ActivityTable } from "@/components/ActivityTable";
import { RecoveryFunnel } from "@/components/RecoveryFunnel";
import { RecoveryChart } from "@/components/RecoveryChart";
import { useRecoveryFunnel } from "@/hooks/useRecoveryFunnel";
import { PageContext } from "@/components/PageContext";

const actions: TriageAction[] = [
  "retry_same_rail",
  "retry_alt_rail",
  "escalate_to_dunning",
  "hold_for_review",
  "no_action",
];

export function DashboardPage() {
  const [scope, setScope] = useState<"session" | "all">("session");
  const { transactions, error: txError } = useRecentTransactions(50, scope);
  const funnel = useRecoveryFunnel(scope);
  const summary = funnel.summary;
  const error = txError || funnel.error;

  const atRisk = summary?.attempted_volume_inr ?? transactions.reduce(
    (total, item) => total + item.amount_inr,
    0,
  );
  const recovered = summary?.recovered_volume_inr ?? transactions.reduce(
    (total, item) => total + (item.recovery_outcome?.actual_recovered_inr ?? 0),
    0,
  );
  const expected = summary?.expected_recovery_inr ?? transactions.reduce(
    (total, item) => total + (item.selected_expected_net_recovery_inr ?? 0),
    0,
  );

  const pendingReviewCount = summary?.pending_review_count ?? transactions.filter(
    (item) =>
      item.action === "hold_for_review" ||
      item.recovery_outcome?.execution_status === "HELD" ||
      (!item.recovery_outcome && item.action !== "no_action"),
  ).length;

  const pendingReviewVolume = summary?.pending_review_volume_inr ?? transactions
    .filter(
      (item) =>
        item.action === "hold_for_review" ||
        item.recovery_outcome?.execution_status === "HELD" ||
        (!item.recovery_outcome && item.action !== "no_action"),
    )
    .reduce((total, item) => total + item.amount_inr, 0);

  const resolvedCount = summary?.resolved_count ?? (transactions.length - pendingReviewCount);
  const resolvedVolume = summary?.resolved_volume_inr ?? Math.max(0, atRisk - pendingReviewVolume);

  const recoveryRate = summary?.recovery_rate_pct != null
    ? `${summary.recovery_rate_pct.toFixed(1)}%`
    : resolvedVolume > 0
      ? `${((recovered / resolvedVolume) * 100).toFixed(1)}%`
      : "Unavailable";

  const breakdown = actions.map((action) => ({
    action: ACTION_LABELS[action],
    count: transactions.filter((item) => item.action === action).length,
  }));

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="REVENUE RECOVERY OPERATIONS"
        title="Dashboard"
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


      {/* 1. SCOPE CONSISTENCY: Explicit toggle between "This session" (default) and "All-time" */}
      <div className="panel" data-tour="scope-and-funnel" style={{ padding: "0.875rem 1.25rem", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "0.75rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.875rem", flexWrap: "wrap" }}>
          <span style={{ fontSize: "0.8125rem", fontWeight: "700", color: "var(--text-secondary, #475569)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
            Metrics Scope:
          </span>
          <div className="segmented" role="tablist" aria-label="Metrics scope">
            <button
              type="button"
              className={scope === "session" ? "active" : ""}
              onClick={() => setScope("session")}
              style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}
            >
              <span style={{ display: "inline-block", width: "7px", height: "7px", borderRadius: "50%", background: scope === "session" ? "var(--brand-primary, #0284c7)" : "#94a3b8" }} />
              This session (Live Mode)
            </button>
            <button
              type="button"
              className={scope === "all" ? "active" : ""}
              onClick={() => setScope("all")}
            >
              All-time (Full Archive)
            </button>
          </div>
        </div>
        <span style={{ fontSize: "0.8125rem", color: "var(--text-tertiary, #64748b)" }}>
          {scope === "session"
            ? "Scoped to current live demo session. Seed and past evaluation benchmark data excluded."
            : "Showing all-time database totals across every recorded seed and benchmark run."}
        </span>
      </div>

      {/* Synchronized Recovery Ticker and Recovery Funnel sharing the same selected scope */}
      <RecoveryChart {...funnel} scope={scope} />
      <RecoveryFunnel {...funnel} scope={scope} />

      {/* 2. RECOVERY RATE HONESTY: KPI grid using active scope with honest recovery rate + pending review */}
      <div className="kpi-grid">
        <KpiCard
          label="Revenue at risk"
          value={money(atRisk)}
          detail={scope === "session" ? "Failed payments in active session" : "All historical failed payments"}
        />
        <KpiCard
          label="Revenue recovered"
          value={money(recovered)}
          detail="Measured outcomes only"
          positive
        />
        <KpiCard
          label="Recovery rate"
          value={recoveryRate}
          detail={`Measured recovered ÷ resolved cases (${pendingReviewCount} pending review excluded)`}
        />
        <KpiCard
          label="Pending review"
          value={String(pendingReviewCount)}
          detail={`${money(pendingReviewVolume)} held awaiting triage — not failures`}
        />
        <KpiCard
          label="Resolved cases"
          value={String(resolvedCount)}
          detail={`${money(resolvedVolume)} evaluated with known outcome`}
        />
        <KpiCard
          label="Expected recovery"
          value={money(expected)}
          detail="Expected net; not actual revenue"
        />
      </div>

      <div className="content-grid content-grid-wide">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Recovery performance</h2>
              <p>Selected action mix ({scope === "session" ? "active session" : "all-time"}).</p>
            </div>
            <span className={`badge ${scope === "session" ? "badge-sim" : "badge-neutral"}`}>
              {scope === "session" ? "LIVE VIEW" : "ALL-TIME VIEW"}
            </span>
          </div>
          <div className="chart-wrap">
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={breakdown}>
                <CartesianGrid stroke={chartGrid} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="action" axisLine={chartAxis} tickLine={chartAxis} tick={chartTick} />
                <YAxis allowDecimals={false} axisLine={chartAxis} tickLine={chartAxis} tick={chartTick} />
                <Tooltip contentStyle={chartTooltipStyle} labelStyle={chartTooltipLabelStyle} itemStyle={chartTooltipItemStyle} cursor={chartCursor} />
                <Bar
                  dataKey="count"
                  name="Decisions"
                  fill="var(--chart-primary)"
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

      <section className="panel" data-tour="live-decision-feed">
        <div className="panel-heading">
          <div>
            <h2>Recent recovery activity</h2>
            <p>Latest payment failures and their lifecycle ({scope === "session" ? "active session" : "all-time"}).</p>
          </div>
          <Link to="/audit" className="text-link">
            Open audit trail
          </Link>
        </div>
        {transactions.length === 0 ? (
          <div className="state">
            {scope === "session"
              ? "No live mode transactions in this session yet. Click 'Start Live Mode' in the navigation bar to start playback."
              : "No recovery activity recorded in database yet."}
          </div>
        ) : (
          <ActivityTable 
            transactions={transactions.slice(0, 8)} 
          />
        )}
      </section>

      {/* 3. NARRATIVE: How RECOVR works explainer (Shrunk and moved down) */}
      <section className="panel" data-tour="how-recovr-works">
        <div className="panel-heading">
          <div>
            <h2>How RECOVR Works</h2>
            <p>Autonomous payment failure triage</p>
          </div>
          <Link to="/settings" className="text-link">Learn more in Settings →</Link>
        </div>
        <p style={{ fontSize: "0.875rem", lineHeight: "1.6", color: "var(--text-secondary, #475569)", marginTop: "0.75rem" }}>
          RECOVR operates as an AI-powered triage agent for failed payments. Instead of relying on static retry rules, it uses a pipeline of deterministic checks and LLM-driven reasoning to evaluate each failure's context and select the optimal recovery action based on expected economic value.
        </p>
      </section>

      <PageContext>
        This dashboard gives you a high-level view of your failed payment recovery operations. The funnel and ticker show the volume of failed payments processed and the amount of revenue successfully recovered. By default, this view is scoped to the current active session, but you can toggle it to see all-time historical performance.
      </PageContext>
    </div>
  );
}


