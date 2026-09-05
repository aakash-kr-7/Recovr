/** Shared Recharts overrides so axes/tooltips follow Blade tokens, not Recharts defaults. */
export const chartTooltipStyle = {
  backgroundColor: "var(--surface-raised)",
  border: "1px solid var(--border-subtle)",
  borderRadius: 8,
  color: "var(--text-primary)",
};

export const chartTooltipLabelStyle = { color: "var(--text-primary)" };
export const chartTooltipItemStyle = { color: "var(--text-primary)" };
export const chartTick = { fill: "var(--chart-text)", fontSize: 11 };
export const chartTickSmall = { fill: "var(--chart-text)", fontSize: 10 };
export const chartAxis = { stroke: "var(--chart-axis)" };
export const chartGrid = "var(--chart-grid)";
export const chartCursor = { fill: "var(--chart-cursor)" };
