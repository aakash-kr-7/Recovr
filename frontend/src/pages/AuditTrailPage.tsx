import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";
import { ACTION_LABELS, money } from "@/lib/operations";
import type { RecentTransaction, TriageAction } from "@/types/api";
import { PageHeader } from "@/components/PageHeader";
import { PageContext } from "@/components/PageContext";

type PathFilter = "all" | "deterministic" | "reasoning";

function ConfidenceMeter({ value }: { value: number | null }) {
  if (value === null || value === undefined) {
    return <span className="audit-confidence-na">N/A</span>;
  }
  const pct = Math.round(value * 100);
  const color =
    pct >= 80
      ? "var(--chart-positive, #13825f)"
      : pct >= 50
        ? "var(--chart-notice, #9a6b25)"
        : "#ad334d";
  return (
    <div className="audit-confidence">
      <div className="audit-confidence-bar">
        <div
          className="audit-confidence-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="audit-confidence-label" style={{ color }}>
        {pct}%
      </span>
    </div>
  );
}

function EventCard({ item }: { item: RecentTransaction }) {
  const isAI = item.path_taken === "reasoning";
  const outcomeStatus =
    item.recovery_outcome?.execution_status?.toUpperCase() ?? "PENDING";
  const isRecovered =
    item.recovery_outcome?.actual_recovered_inr != null &&
    item.recovery_outcome.actual_recovered_inr > 0;

  return (
    <div className={`audit-event-card ${isAI ? "audit-event-card--ai" : "audit-event-card--rule"}`}>
      {/* Header row */}
      <div className="audit-event-header">
        <div className="audit-event-path-badge">
          <span
            className={`audit-path-indicator ${isAI ? "audit-path-indicator--ai" : "audit-path-indicator--rule"}`}
          />
          {isAI ? "AI reasoning" : "Deterministic rule"}
        </div>
        <time className="audit-event-time">
          {new Date(item.created_at).toLocaleString()}
        </time>
      </div>

      {/* Body */}
      <div className="audit-event-body">
        <div className="audit-event-col">
          <span className="audit-event-label">Transaction</span>
          <Link
            className="table-link"
            to={`/decisions/${item.transaction_id}`}
          >
            {item.transaction_id.slice(0, 16)}…
          </Link>
        </div>
        <div className="audit-event-col">
          <span className="audit-event-label">Failure</span>
          <span className="audit-event-value">{item.decline_reason}</span>
        </div>
        <div className="audit-event-col">
          <span className="audit-event-label">Action taken</span>
          <span className="audit-event-action">{ACTION_LABELS[item.action]}</span>
        </div>
        <div className="audit-event-col">
          <span className="audit-event-label">Confidence</span>
          <ConfidenceMeter value={item.confidence} />
        </div>
        <div className="audit-event-col">
          <span className="audit-event-label">Expected net</span>
          <span className="audit-event-value">
            {money(item.selected_expected_net_recovery_inr)}
          </span>
        </div>
        <div className="audit-event-col">
          <span className="audit-event-label">Execution</span>
          <span className="audit-event-value audit-event-status">
            {item.recovery_outcome?.mode === "REAL_RAZORPAY_ACTION"
              ? "Real · Razorpay"
              : item.is_synthetic ||
                  item.recovery_outcome?.mode === "BOUNDED_SIMULATION"
                ? "Simulated"
                : "Internal"}
          </span>
        </div>
        <div className="audit-event-col">
          <span className="audit-event-label">Outcome</span>
          <span
            className={`audit-outcome-pill ${
              isRecovered
                ? "audit-outcome-pill--success"
                : outcomeStatus === "FAILED" || outcomeStatus === "FAILED_TO_EXECUTE"
                  ? "audit-outcome-pill--fail"
                  : outcomeStatus === "HELD" || outcomeStatus === "SKIPPED"
                    ? "audit-outcome-pill--held"
                    : "audit-outcome-pill--pending"
            }`}
          >
            {isRecovered
              ? "Recovered"
              : outcomeStatus === "FAILED" || outcomeStatus === "FAILED_TO_EXECUTE"
                ? "Failed"
                : outcomeStatus === "HELD" || outcomeStatus === "SKIPPED"
                  ? "Held"
                  : outcomeStatus === "SIMULATED"
                    ? "Simulated"
                    : "Pending"}
          </span>
        </div>
      </div>

      {/* Reasoning excerpt (only for AI path) */}
      {isAI && item.reasoning_text && (
        <div className="audit-reasoning-excerpt">
          <span className="audit-event-label">AI reasoning</span>
          <p>{item.reasoning_text.length > 200
            ? item.reasoning_text.slice(0, 200) + "…"
            : item.reasoning_text}
          </p>
        </div>
      )}
    </div>
  );
}

export function AuditTrailPage() {
  const { transactions, loading, error } = useRecentTransactions(200);
  const [pathFilter, setPathFilter] = useState<PathFilter>("all");
  const [actionFilter, setActionFilter] = useState<TriageAction | "all">(
    "all",
  );

  const rows = useMemo(
    () =>
      transactions.filter(
        (item) =>
          (actionFilter === "all" || item.action === actionFilter) &&
          (pathFilter === "all" || item.path_taken === pathFilter),
      ),
    [transactions, actionFilter, pathFilter],
  );

  /* Stats for the header badges */
  const stats = useMemo(() => {
    let aiCount = 0;
    let ruleCount = 0;
    for (const tx of transactions) {
      if (tx.path_taken === "reasoning") aiCount++;
      else ruleCount++;
    }
    return { aiCount, ruleCount, total: transactions.length };
  }, [transactions]);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="TRACEABILITY · DECISION LOG"
        title="Audit trail"
        description="Forensic record of every triage decision. Inspect how and why each recovery action was chosen — trace the reasoning, confidence scores, and execution outcomes."
      >
        <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
          <span className="badge badge-provider">
            {stats.aiCount} AI decisions
          </span>
          <span className="badge badge-neutral">
            {stats.ruleCount} rule-based
          </span>
        </div>
      </PageHeader>

      {/* ── Path segmented control + filter ── */}
      <div className="audit-controls">
        <div
          className="segmented"
          role="tablist"
          aria-label="Filter by decision path"
        >
          <button
            type="button"
            className={pathFilter === "all" ? "active" : ""}
            onClick={() => setPathFilter("all")}
          >
            All paths ({stats.total})
          </button>
          <button
            type="button"
            className={pathFilter === "reasoning" ? "active" : ""}
            onClick={() => setPathFilter("reasoning")}
            style={{ display: "flex", alignItems: "center", gap: "5px" }}
          >
            <span className="audit-path-indicator audit-path-indicator--ai" />
            AI reasoning ({stats.aiCount})
          </button>
          <button
            type="button"
            className={pathFilter === "deterministic" ? "active" : ""}
            onClick={() => setPathFilter("deterministic")}
            style={{ display: "flex", alignItems: "center", gap: "5px" }}
          >
            <span className="audit-path-indicator audit-path-indicator--rule" />
            Deterministic ({stats.ruleCount})
          </button>
        </div>
        <div className="filter-bar">
          <label>
            Action
            <select
              value={actionFilter}
              onChange={(event) =>
                setActionFilter(event.target.value as TriageAction | "all")
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
        </div>
      </div>

      {/* ── Event cards timeline ── */}
      {loading && !transactions.length ? (
        <div className="state">Loading audit trail…</div>
      ) : error ? (
        <div className="state state-error">{error}</div>
      ) : !rows.length ? (
        <div className="state">No audit events match these filters.</div>
      ) : (
        <div className="audit-timeline" data-tour="audit-filters">
          {rows.map((item) => (
            <EventCard key={item.transaction_id} item={item} />
          ))}
        </div>
      )}

      <PageContext>
        This log shows HOW each decision was reasoned, not just what happened.
        Confidence scores only appear for AI-informed decisions — deterministic
        rules fire with fixed logic and don't produce confidence. Use this
        view for compliance review, debugging AI behaviour, and tracing the
        full decision lifecycle.
      </PageContext>
    </div>
  );
}
