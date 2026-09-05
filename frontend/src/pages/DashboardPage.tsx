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
import { HOW_RECOVR_WORKS } from "@/content/explainer";

const actions: TriageAction[] = [
  "retry_same_rail",
  "retry_alt_rail",
  "escalate_to_dunning",
  "hold_for_review",
  "no_action",
];

export function DashboardPage() {
  const [hoveredTx, setHoveredTx] = useState<RecentTransaction | null>(null);
  const { transactions, loading, error } = useRecentTransactions();
  const funnel = useRecoveryFunnel();
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
      <RecoveryChart {...funnel} />
      <RecoveryFunnel {...funnel} />
      {loading && transactions.length === 0 ? (
        <>
          <div className="state" data-tour="decision-flow">Loading the decision flow…</div>
          <div className="state" data-tour="live-decision-feed">Loading live recovery activity…</div>
        </>
      ) : transactions.length === 0 ? (
        <>
          <div className="state" data-tour="decision-flow">
            The decision flow will appear here when a failed payment reaches triage.
          </div>
          <div className="state" data-tour="live-decision-feed">
            No recovery activity yet. Incoming failed payments will appear here after triage.
          </div>
        </>
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
          <section className="panel" data-tour="decision-flow" title={HOW_RECOVR_WORKS.summary}>
            <div className="panel-heading">
              <div>
                <h2>Decision pipeline</h2>
                <p>Hover over a transaction in the live feed to trace its execution path.</p>
              </div>
            </div>
            <PipelineDiagram hoveredTx={hoveredTx} />
          </section>
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
                <p>Latest payment failures and their lifecycle.</p>
              </div>
              <Link to="/audit" className="text-link">
                Open audit trail
              </Link>
            </div>
            <ActivityTable 
              transactions={transactions.slice(0, 8)} 
              onHoverTransaction={setHoveredTx} 
            />
          </section>
        </>
      )}
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
