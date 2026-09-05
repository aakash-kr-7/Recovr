import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  chartAxis,
  chartGrid,
  chartTick,
  chartTooltipItemStyle,
  chartTooltipLabelStyle,
  chartTooltipStyle,
} from "@/lib/chartTheme";
import { useEvaluationReport } from "@/hooks/useEvaluationReport";
import { money, percent } from "@/lib/operations";
import type { PolicyMetrics } from "@/types/api";
import { PageHeader } from "@/components/PageHeader";
import { KpiCard } from "@/components/KpiCard";

type View = "unconstrained" | "constrained";
const policies: {
  key: "retry_all_same_rail" | "fixed_rule_policy" | "recovr";
  label: string;
}[] = [
  { key: "retry_all_same_rail", label: "Retry All" },
  { key: "fixed_rule_policy", label: "Fixed Rule" },
  { key: "recovr", label: "RECOVR" },
];

export function ResultsPage() {
  const { report, loading, error } = useEvaluationReport();
  const [view, setView] = useState<View>("unconstrained");
  if (loading)
    return (
      <div className="page-stack">
        <div className="state" data-tour="calibration-chart">Loading evaluation report…</div>
      </div>
    );
  if (error || !report)
    return (
      <div className="page-stack">
        <div className="state state-error" data-tour="calibration-chart">
          Evaluation unavailable. {error ?? "No report found."}
        </div>
      </div>
    );
  const values = report[view];
  const recovr = values.recovr;
  const retryAll = values.retry_all_same_rail;
  const fixed = values.fixed_rule_policy;
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="AI DECISION AUDIT · SIMULATED / SYNTHETIC"
        title="Recovery performance"
        description="Held-out action-level evaluation. These figures are simulated and never represent actual merchant revenue."
      >
        <span className="badge badge-sim">SYNTHETIC HOLDOUT</span>
      </PageHeader>
      <div className="kpi-grid">
        <KpiCard
          label="Amount at risk"
          value={money(recovr.total_amount_at_risk_inr)}
          detail="SIMULATED / SYNTHETIC"
        />
        <KpiCard
          label="RECOVR net recovery"
          value={money(recovr.net_recovery_inr)}
          detail="SIMULATED / SYNTHETIC"
          positive
        />
        <KpiCard
          label="Best possible net recovery"
          value={money(recovr.true_expected_net_value_inr)}
          detail="SIMULATED / SYNTHETIC"
        />
        <KpiCard
          label="Incremental vs retry-all"
          value={money(recovr.net_recovery_inr - retryAll.net_recovery_inr)}
          detail="SIMULATED / SYNTHETIC"
          positive
        />
        <KpiCard
          label="Expected regret"
          value={money(recovr.expected_regret_inr)}
          detail="SIMULATED / SYNTHETIC"
        />
        <KpiCard
          label="Realized regret"
          value={money(recovr.realized_regret_inr)}
          detail="SIMULATED / SYNTHETIC"
        />
        <KpiCard
          label="Recovery rate"
          value={percent(recovr.recovery_rate_by_inr)}
          detail="SIMULATED / SYNTHETIC"
        />
        <KpiCard
          label="Incremental vs fixed rules"
          value={money(recovr.net_recovery_inr - fixed.net_recovery_inr)}
          detail="SIMULATED / SYNTHETIC"
          positive
        />
      </div>
      <section className="panel" data-tour="calibration-chart">
        <div className="panel-heading">
          <div>
            <h2>Baseline comparison</h2>
            <p>Policies are compared within the same execution constraint.</p>
          </div>
          <div
            className="segmented"
            role="tablist"
            aria-label="Evaluation view"
          >
            <button
              className={view === "unconstrained" ? "active" : ""}
              onClick={() => setView("unconstrained")}
            >
              Unconstrained decision quality
            </button>
            <button
              className={view === "constrained" ? "active" : ""}
              onClick={() => setView("constrained")}
            >
              Constrained execution quality
            </button>
          </div>
        </div>
        <div className="table-scroll">
          <table className="operations-table comparison-table">
            <thead>
              <tr>
                <th>Policy</th>
                <th>Net recovery</th>
                <th>Recovery rate</th>
                <th>Expected regret</th>
                <th>Realized regret</th>
                <th>Incremental value</th>
              </tr>
            </thead>
            <tbody>
              {policies.map(({ key, label }) => {
                const policy = values[key];
                return (
                  <tr
                    key={key}
                    className={key === "recovr" ? "selected-row" : ""}
                  >
                    <td>
                      <strong>{label}</strong>
                      {key === "recovr" && (
                        <span className="badge badge-positive">
                          RECOMMENDED
                        </span>
                      )}
                    </td>
                    <td>{money(policy.net_recovery_inr)}</td>
                    <td>{percent(policy.recovery_rate_by_inr)}</td>
                    <td>{money(policy.expected_regret_inr)}</td>
                    <td>{money(policy.realized_regret_inr)}</td>
                    <td>
                      {key === "recovr"
                        ? "—"
                        : money(
                            recovr.net_recovery_inr - policy.net_recovery_inr,
                          )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="table-note">
          Best possible is the hidden conditional expected-net reference used
          solely for regret analysis. It is not an executable merchant result.
        </p>
      </section>
      <section className="content-grid">
        <section className="panel">
          <h2>RECOVR action distribution</h2>
          <ActionDistribution policy={recovr} />
        </section>
        <section className="panel">
          <h2>Evaluation scope</h2>
          <dl className="definition-list">
            <div>
              <dt>Holdout cases</dt>
              <dd>{report.holdout_set_size}</dd>
            </div>
            <div>
              <dt>Evaluation version</dt>
              <dd>{report.evaluation_version}</dd>
            </div>
            <div>
              <dt>Generated</dt>
              <dd>{new Date(report.generated_at).toLocaleString()}</dd>
            </div>
            <div>
              <dt>Execution overrides</dt>
              <dd>{report.evaluation_views.cap_induced_execution_overrides}</dd>
            </div>
          </dl>
        </section>
      </section>
      <section className="panel">
        <h2>Calibration reliability</h2>
        <p>Comparing predicted probability against realized recovery rate on the holdout evaluation set. Perfect calibration follows the dotted line.</p>
        <div style={{ width: "100%", height: 320, marginTop: "1rem" }}>
          {report.calibration && report.calibration.length > 0 ? (
            <ResponsiveContainer>
              <LineChart
                data={report.calibration}
                margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
              >
                <CartesianGrid stroke={chartGrid} strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="expected_probability"
                  type="number"
                  domain={[0, 1]}
                  tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                  stroke="var(--chart-axis)"
                  axisLine={chartAxis}
                  tickLine={chartAxis}
                  tick={chartTick}
                  name="Predicted Probability"
                />
                <YAxis
                  dataKey="observed_recovery_rate"
                  type="number"
                  domain={[0, 1]}
                  tickFormatter={(val) => `${(val * 100).toFixed(0)}%`}
                  stroke="var(--chart-axis)"
                  axisLine={chartAxis}
                  tickLine={chartAxis}
                  tick={chartTick}
                  name="Observed Recovery"
                />
                <Tooltip
                  contentStyle={chartTooltipStyle}
                  labelStyle={chartTooltipLabelStyle}
                  itemStyle={chartTooltipItemStyle}
                  formatter={(value: number, name: string) => [
                    `${(value * 100).toFixed(1)}%`,
                    name === "observed_recovery_rate" ? "Observed Recovery" : name,
                  ]}
                  labelFormatter={(label) => `Expected: ${(Number(label) * 100).toFixed(1)}%`}
                />
                <ReferenceLine
                  segment={[
                    { x: 0, y: 0 },
                    { x: 1, y: 1 },
                  ]}
                  stroke="var(--chart-grid)"
                  strokeDasharray="4 4"
                />
                <Line
                  type="monotone"
                  dataKey="observed_recovery_rate"
                  stroke="var(--chart-primary)"
                  strokeWidth={3}
                  dot={{ fill: "var(--surface-base)", stroke: "var(--chart-primary)", strokeWidth: 2, r: 5 }}
                  activeDot={{ r: 7 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="state">No calibration data available in the evaluation report.</div>
          )}
        </div>
      </section>
      <p className="footnote">
        {report.note} Legacy binary retry diagnostics have deliberately been
        removed from this primary view.
      </p>
    </div>
  );
}

function ActionDistribution({ policy }: { policy: PolicyMetrics }) {
  return (
    <div className="health-list">
      {Object.entries(policy.action_distribution).map(([action, count]) => (
        <div key={action}>
          <span>{action.replace(/_/g, " ")}</span>
          <strong>{count}</strong>
        </div>
      ))}
    </div>
  );
}
