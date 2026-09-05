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
import type { RecentTransaction, TriageAction } from "@/types/api";
import { PageHeader } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";
import { ActivityTable } from "@/components/ActivityTable";
import { RecoveryFunnel } from "@/components/RecoveryFunnel";
import { RecoveryChart } from "@/components/RecoveryChart";
import { useRecoveryFunnel } from "@/hooks/useRecoveryFunnel";
import { HOW_RECOVR_WORKS_TITLE, HOW_RECOVR_WORKS_SUMMARY } from "@/content/explainer";

const actions: TriageAction[] = [
  "retry_same_rail",
  "retry_alt_rail",
  "escalate_to_dunning",
  "hold_for_review",
  "no_action",
];

export function DashboardPage() {
  const [scope, setScope] = useState<"session" | "all">("session");
  const [hoveredTx, setHoveredTx] = useState<RecentTransaction | null>(null);
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

      {/* 3. NARRATIVE: How RECOVR works explainer + Pipeline diagram in same top viewport */}
      <section className="panel" data-tour="how-recovr-works">
        <div className="panel-heading">
          <div>
            <h2>{HOW_RECOVR_WORKS_TITLE}</h2>
            <p>How the autonomous payment failure triage and recovery pipeline thinks</p>
          </div>
          <span className="badge badge-primary">PIPELINE ARCHITECTURE</span>
        </div>
        <div style={{ marginTop: "0.75rem" }}>
          <p style={{ fontSize: "0.875rem", lineHeight: "1.6", color: "var(--text-secondary, #475569)", marginBottom: "1rem" }}>
            {HOW_RECOVR_WORKS_SUMMARY}
          </p>
          <div style={{ borderTop: "1px solid var(--border-subtle, #e2e8f0)", paddingTop: "0.75rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.25rem", flexWrap: "wrap", gap: "0.5rem" }}>
              <span style={{ fontSize: "0.8125rem", fontWeight: "600", color: "var(--text-primary, #0f172a)" }}>
                Interactive decision pipeline
              </span>
              <span style={{ fontSize: "0.75rem", color: "var(--text-tertiary, #94a3b8)" }}>
                Hover over any transaction in the live feed below to trace its path:
              </span>
            </div>
            <PipelineDiagram hoveredTx={hoveredTx} />
          </div>
        </div>
      </section>

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
            onHoverTransaction={setHoveredTx} 
          />
        )}
      </section>
    </div>
  );
}

function PipelineDiagram({ hoveredTx }: { hoveredTx: RecentTransaction | null }) {
  const isDet = hoveredTx?.path_taken === "deterministic";
  const isRes = hoveredTx?.path_taken === "reasoning";
  const isActive = hoveredTx !== null;

  const activeColor = "var(--brand-primary)";
  const inactiveColor = "var(--border-strong, #9ca3af)";
  
  const boxFill = (active: boolean) => active ? "var(--brand-subtle)" : "transparent";
  const boxStroke = (active: boolean) => active ? activeColor : inactiveColor;
  const textColor = (active: boolean) => active ? activeColor : "var(--text-secondary)";

  return (
    <div className="pipeline-diagram-wrapper" style={{ width: "100%", overflowX: "auto", padding: "1rem 0" }}>
      <svg viewBox="0 0 850 120" style={{ width: "100%", minWidth: "700px", height: "auto" }}>
        <defs>
          <marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" fill={inactiveColor} />
          </marker>
          <marker id="arrow-active" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto" markerUnits="strokeWidth">
            <path d="M0,0 L0,6 L9,3 z" fill={activeColor} />
          </marker>
        </defs>
        
        {/* Edges */}
        <path d="M 120 60 L 155 60" stroke={boxStroke(isActive)} strokeWidth={2} fill="none" markerEnd={isActive ? "url(#arrow-active)" : "url(#arrow)"} />
        <path d="M 240 60 L 270 60 L 270 30 L 285 30" stroke={boxStroke(isDet)} strokeWidth={2} fill="none" markerEnd={isDet ? "url(#arrow-active)" : "url(#arrow)"} />
        <path d="M 240 60 L 270 60 L 270 90 L 285 90" stroke={boxStroke(isRes)} strokeWidth={2} fill="none" markerEnd={isRes ? "url(#arrow-active)" : "url(#arrow)"} />
        <path d="M 410 30 L 430 30 L 430 60 L 445 60" stroke={boxStroke(isDet)} strokeWidth={2} fill="none" markerEnd={isDet ? "url(#arrow-active)" : "url(#arrow)"} />
        <path d="M 410 90 L 430 90 L 430 60 L 445 60" stroke={boxStroke(isRes)} strokeWidth={2} fill="none" markerEnd={isRes ? "url(#arrow-active)" : "url(#arrow)"} />
        <path d="M 570 60 L 605 60" stroke={boxStroke(isActive)} strokeWidth={2} fill="none" markerEnd={isActive ? "url(#arrow-active)" : "url(#arrow)"} />
        <path d="M 730 60 L 765 60" stroke={boxStroke(isActive)} strokeWidth={2} fill="none" markerEnd={isActive ? "url(#arrow-active)" : "url(#arrow)"} />

        {/* Nodes */}
        <g transform="translate(10, 45)">
          <rect width="110" height="30" rx="4" fill={boxFill(isActive)} stroke={boxStroke(isActive)} strokeWidth={2} />
          <text x="55" y="19" fontSize="11" fontWeight="600" textAnchor="middle" fill={textColor(isActive)}>Payment Failed</text>
        </g>
        
        <g transform="translate(160, 45)">
          <rect width="80" height="30" rx="4" fill={boxFill(isActive)} stroke={boxStroke(isActive)} strokeWidth={2} />
          <text x="40" y="19" fontSize="11" fontWeight="600" textAnchor="middle" fill={textColor(isActive)}>Gate</text>
        </g>

        <g transform="translate(290, 15)">
          <rect width="120" height="30" rx="4" fill={boxFill(isDet)} stroke={boxStroke(isDet)} strokeWidth={2} />
          <text x="60" y="19" fontSize="11" fontWeight="600" textAnchor="middle" fill={textColor(isDet)}>Deterministic Path</text>
        </g>

        <g transform="translate(290, 75)">
          <rect width="120" height="30" rx="4" fill={boxFill(isRes)} stroke={boxStroke(isRes)} strokeWidth={2} />
          <text x="60" y="19" fontSize="11" fontWeight="600" textAnchor="middle" fill={textColor(isRes)}>Reasoning Path</text>
        </g>

        <g transform="translate(450, 45)">
          <rect width="120" height="30" rx="4" fill={boxFill(isActive)} stroke={boxStroke(isActive)} strokeWidth={2} />
          <text x="60" y="19" fontSize="11" fontWeight="600" textAnchor="middle" fill={textColor(isActive)}>Economic Scoring</text>
        </g>

        <g transform="translate(610, 45)">
          <rect width="120" height="30" rx="4" fill={boxFill(isActive)} stroke={boxStroke(isActive)} strokeWidth={2} />
          <text x="60" y="19" fontSize="11" fontWeight="600" textAnchor="middle" fill={textColor(isActive)}>Bounded Executor</text>
        </g>

        <g transform="translate(770, 45)">
          <rect width="70" height="30" rx="4" fill={boxFill(isActive)} stroke={boxStroke(isActive)} strokeWidth={2} />
          <text x="35" y="19" fontSize="11" fontWeight="600" textAnchor="middle" fill={textColor(isActive)}>Outcome</text>
        </g>

      </svg>
    </div>
  );
}
