import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { money } from "@/lib/operations";
import type { RecoveryFunnelSummary } from "@/types/api";

interface RecoveryFunnelProps {
  summary: RecoveryFunnelSummary | null;
  loading: boolean;
  error: string | null;
}

export function RecoveryFunnel({ summary, loading, error }: RecoveryFunnelProps) {
  if (loading && !summary) return <div className="state">Loading recovery funnel…</div>;
  if (error && !summary) return <div className="state state-error">Recovery funnel unavailable. {error}</div>;

  const data = summary
    ? [
        { stage: "Total attempted", volume: summary.attempted_volume_inr, color: "#3158c8" },
        { stage: "Failed / unresolved", volume: summary.failed_volume_inr, color: "#9a6b25" },
        { stage: "Recovered", volume: summary.recovered_volume_inr, color: "#13825f" },
      ]
    : [];

  return (
    <section className="panel recovery-funnel-panel" data-tour="recovery-funnel" aria-labelledby="recovery-funnel-title">
      <div className="panel-heading">
        <div>
          <h2 id="recovery-funnel-title">Recovery funnel</h2>
          <p>Measured recovery only; pending outcomes remain in failed volume.</p>
        </div>
        <span className="badge badge-neutral">{summary?.transaction_count ?? 0} ATTEMPTS</span>
      </div>
      <div className="recovery-funnel-chart">
        <ResponsiveContainer width="100%" height={190}>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 84, bottom: 0, left: 18 }}>
            <XAxis type="number" hide />
            <YAxis dataKey="stage" type="category" width={132} tick={{ fontSize: 11, fill: "#58657a" }} />
            <Tooltip formatter={(value: number) => money(value)} cursor={{ fill: "#f6f8fb" }} />
            <Bar dataKey="volume" name="Volume" radius={[0, 3, 3, 0]}>
              {data.map((entry) => <Cell key={entry.stage} fill={entry.color} />)}
              <LabelList dataKey="volume" position="right" formatter={(value: number) => money(value)} fill="#435168" fontSize={11} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {error && <p className="table-note">Last refresh failed: {error}</p>}
    </section>
  );
}
