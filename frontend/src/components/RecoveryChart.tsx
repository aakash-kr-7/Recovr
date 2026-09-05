import { useEffect, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  chartAxis,
  chartGrid,
  chartTickSmall,
  chartTooltipItemStyle,
  chartTooltipLabelStyle,
  chartTooltipStyle,
} from "@/lib/chartTheme";
import { money } from "@/lib/operations";
import type { RecoveryFunnelSummary } from "@/types/api";

interface RecoveryChartProps {
  summary: RecoveryFunnelSummary | null;
  loading: boolean;
  error: string | null;
  scope?: "session" | "all";
}

function AnimatedMoney({ value }: { value: number }) {
  const [displayed, setDisplayed] = useState(value);
  const previous = useRef(value);

  useEffect(() => {
    const start = previous.current;
    const duration = 650;
    const startedAt = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const progress = Math.min((now - startedAt) / duration, 1);
      setDisplayed(start + (value - start) * progress);
      if (progress < 1) frame = requestAnimationFrame(tick);
      else previous.current = value;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return <strong className="recovered-counter-value">{money(displayed)}</strong>;
}

export function RecoveryChart({ summary, loading, error, scope }: RecoveryChartProps) {
  const activeScope = scope ?? summary?.scope ?? "session";
  const isSession = activeScope === "session";
  const timeline = summary?.recovery_timeline ?? [];
  const hasRecovery = timeline.some((point) => point.cumulative_recovered_inr > 0);
  const chartData = timeline.map((point) => ({
    ...point,
    time: new Date(point.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  }));

  return (
    <section className="panel recovered-counter-panel" aria-labelledby="recovered-counter-title">
      <div className="recovered-counter-copy">
        <p className="eyebrow">{isSession ? "THIS SESSION MEASURED RECOVERY" : "ALL-TIME MEASURED RECOVERY"}</p>
        <h2 id="recovered-counter-title">₹ recovered so far</h2>
        {loading && !summary ? (
          <div className="recovered-counter-loading">Loading measured outcomes…</div>
        ) : (
          <AnimatedMoney value={summary?.recovered_volume_inr ?? 0} />
        )}
        <p>{isSession ? "Current live session outcomes only. Seed/historical data excluded." : "Confirmed outcomes across full database history."}</p>
      </div>
      <div className="recovered-line-wrap">
        <div className="recovered-line-heading">
          {isSession ? "Cumulative recovery since Live Mode began" : "All-time cumulative recovery"}
        </div>
        {error && !summary ? (
          <div className="state state-error">Recovery history unavailable. {error}</div>
        ) : !hasRecovery ? (
          <div className="recovery-chart-empty">
            No confirmed recovery yet. The line will rise after a recorded successful outcome.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={176}>
            <LineChart data={chartData} margin={{ top: 14, right: 16, bottom: 2, left: 4 }}>
              <CartesianGrid stroke={chartGrid} strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="time" axisLine={chartAxis} tickLine={chartAxis} tick={chartTickSmall} minTickGap={28} />
              <YAxis axisLine={chartAxis} tickLine={chartAxis} tickFormatter={(value: number) => `₹${value}`} tick={chartTickSmall} width={54} />
              <Tooltip contentStyle={chartTooltipStyle} labelStyle={chartTooltipLabelStyle} itemStyle={chartTooltipItemStyle} formatter={(value: number) => money(value)} labelFormatter={(label) => `Time ${label}`} />
              <Line type="stepAfter" dataKey="cumulative_recovered_inr" name="Recovered" stroke="var(--chart-positive)" strokeWidth={2.5} dot={{ r: 3, fill: "var(--chart-positive)" }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
