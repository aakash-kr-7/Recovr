import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/PageHeader";
import { RecoveryChart } from "@/components/RecoveryChart";
import { RecoveryFunnel } from "@/components/RecoveryFunnel";
import { useRecoveryFunnel } from "@/hooks/useRecoveryFunnel";
import { useRecentTransactions } from "@/hooks/useRecentTransactions";
import { OutcomeBadge, StatusBadge } from "@/components/StatusBadges";
import { ACTION_LABELS, money } from "@/lib/operations";
import { api } from "@/lib/api";
import type { LiveModeStatus, RecentTransaction } from "@/types/api";

const LIVE_MODE_PRESETS = [
  {
    step: 1,
    name: "Nighttime bank timeout",
    description:
      "Reasoning path identifies transient bank timeout during off-hours; recommends delayed batch retry.",
  },
  {
    step: 2,
    name: "High-value clean customer",
    description:
      "High confidence in retrying insufficient funds error due to flawless customer payment history.",
  },
  {
    step: 3,
    name: "Stolen card",
    description:
      "Deterministic fast path immediately escalates lost/stolen card to dunning, blocking automatic retries.",
  },
  {
    step: 4,
    name: "Unmapped bank error",
    description:
      "LLM parses unstructured raw bank decline message into an actionable retry strategy.",
  },
  {
    step: 5,
    name: "Repeat offender",
    description:
      "Historical evidence shifts recovery probability downward after repeated identical failures, favoring dunning.",
  },
  {
    step: 6,
    name: "Low-value nuisance",
    description:
      "Fixed retry action costs make holding or no-action optimal for very small amounts to avoid fee burn.",
  },
  {
    step: 7,
    name: "Spend cap in action",
    description:
      "Large payment hits batch spend cap safety bound and is safely held for human operator review.",
  },
  {
    step: 8,
    name: "Genuinely novel bank code",
    description:
      "Reasoning path handles unseen raw host error string (ERR_99_HOST_UNAVAILABLE_RETRY) without breaking.",
  },
  {
    step: 9,
    name: "Account closed",
    description:
      "Fast path isolates terminal account closure and selects NO_ACTION to prevent wasted fees.",
  },
  {
    step: 10,
    name: "Compliance block",
    description:
      "Deterministic rules isolate regulatory/compliance risk and hold it for mandatory human review.",
  },
];

export function LiveModePage() {
  const [liveMode, setLiveMode] = useState<LiveModeStatus | null>(null);
  const [liveModeChanging, setLiveModeChanging] = useState(false);
  const [liveModeError, setLiveModeError] = useState<string | null>(null);

  // Poll status rapidly (1000ms) when running, 2000ms when idle
  useEffect(() => {
    let cancelled = false;
    const fetchStatus = async () => {
      try {
        const status = await api.getLiveModeStatus();
        if (!cancelled) {
          setLiveMode(status);
          setLiveModeError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setLiveModeError(err instanceof Error ? err.message : "Failed to query live mode status");
        }
      }
    };

    void fetchStatus();
    const intervalTime = liveMode?.is_running ? 1000 : 2000;
    const poll = window.setInterval(fetchStatus, intervalTime);
    return () => {
      cancelled = true;
      window.clearInterval(poll);
    };
  }, [liveMode?.is_running]);

  const pollInterval = liveMode?.is_running ? 1000 : 3000;
  const funnel = useRecoveryFunnel("session", pollInterval);
  const { transactions, loading: txLoading, error: txError } = useRecentTransactions(50, "session", pollInterval);

  const isRunning = liveMode?.is_running ?? false;
  const currentStepNum = liveMode?.current_step ?? 0;
  const sequenceLength = liveMode?.sequence_length || LIVE_MODE_PRESETS.length;
  const hasEverRun = currentStepNum > 0 || transactions.length > 0;
  const isCompleted = !isRunning && currentStepNum >= sequenceLength && currentStepNum > 0;

  // Active step metadata
  const activeStepIdx = Math.min(Math.max(1, currentStepNum || 1), LIVE_MODE_PRESETS.length);
  const activePreset = LIVE_MODE_PRESETS[activeStepIdx - 1];

  const currentStepTitle = isRunning
    ? `Step ${activeStepIdx} of ${sequenceLength}: ${liveMode?.current_preset || activePreset.name}`
    : isCompleted
      ? `Sequence Complete · ${sequenceLength} of ${sequenceLength} steps executed`
      : currentStepNum > 0
        ? `Paused at Step ${currentStepNum} of ${sequenceLength}: ${liveMode?.current_preset || activePreset.name}`
        : "Live Mode ready to run";

  const currentStepDescription = isRunning
    ? activePreset.description
    : isCompleted
      ? "All 10 scripted demo scenarios have executed across deterministic rules, LLM reasoning, historical evidence, and safety spend caps."
      : currentStepNum > 0
        ? "Live playback was stopped before completing all 10 steps. Review the transactions triaged so far or restart the sequence."
        : "Click 'Start Live Mode' to execute the 10-step autonomous recovery sequence demonstrating edge cases, LLM reasoning, fast-path rules, and spend caps.";

  const handleStart = async () => {
    setLiveModeChanging(true);
    setLiveModeError(null);
    try {
      await api.startLiveMode();
      setLiveMode(await api.getLiveModeStatus());
    } catch (err) {
      setLiveModeError(err instanceof Error ? err.message : "Failed to start Live Mode");
    } finally {
      setLiveModeChanging(false);
    }
  };

  const handleStop = async () => {
    setLiveModeChanging(true);
    setLiveModeError(null);
    try {
      await api.stopLiveMode();
      setLiveMode(await api.getLiveModeStatus());
    } catch (err) {
      setLiveModeError(err instanceof Error ? err.message : "Failed to stop Live Mode");
    } finally {
      setLiveModeChanging(false);
    }
  };

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="AUTONOMOUS RECOVERY RUNNER · SESSION VIEW"
        title="Live Mode"
        description="Purpose-built command view to observe, present, and narrate autonomous payment failure triage unfolding in real time."
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {isRunning ? (
            <button
              onClick={() => void handleStop()}
              disabled={liveModeChanging}
              className="live-mode-button is-running"
              style={{ padding: "8px 16px", fontSize: "13px" }}
            >
              Stop Live Mode
            </button>
          ) : (
            <button
              onClick={() => void handleStart()}
              disabled={liveModeChanging}
              className="primary-button"
              style={{ padding: "8px 16px", fontSize: "13px" }}
            >
              {hasEverRun ? "Restart Live Mode" : "Start Live Mode"}
            </button>
          )}
        </div>
      </PageHeader>

      {liveModeError && (
        <div className="state state-error">
          Live Mode error: {liveModeError}
        </div>
      )}

      {/* Prominent Current Step Hero Banner */}
      <section className="live-hero-card" aria-label="Current Live Mode Step">
        <div className="live-hero-top">
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <span
              className={`live-state-pill ${
                isRunning ? "running" : isCompleted ? "completed" : currentStepNum > 0 ? "stopped" : "ready"
              }`}
            >
              {isRunning && <span className="pulse-dot" />}
              {isRunning
                ? "● LIVE IN PROGRESS"
                : isCompleted
                  ? "✓ SEQUENCE COMPLETED"
                  : currentStepNum > 0
                    ? "⏸ PAUSED"
                    : "READY TO RUN"}
            </span>
            <span style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: "600" }}>
              Playback pace: ~0.75s per event
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="badge badge-sim">SESSION SCOPE</span>
            <span className="badge badge-neutral">{transactions.length} FIRED</span>
          </div>
        </div>

        <h1 className="live-hero-step-title">{currentStepTitle}</h1>
        <p className="live-hero-step-desc">{currentStepDescription}</p>

        {/* 10-Step Progress Stepper */}
        <div className="live-stepper-wrap">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
            <span style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Sequence Progress (10 Scenarios)
            </span>
            <span style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-primary)" }}>
              {Math.min(currentStepNum, sequenceLength)} of {sequenceLength} steps completed
            </span>
          </div>
          <div className="live-stepper">
            {LIVE_MODE_PRESETS.map((preset) => {
              const isPast = currentStepNum > preset.step;
              const isCurrent = isRunning && activeStepIdx === preset.step;
              const isDone = isCompleted || isPast || (!isRunning && currentStepNum >= preset.step);
              return (
                <div
                  key={preset.step}
                  className={`live-step-pip ${
                    isCurrent ? "active" : isDone ? "completed" : ""
                  }`}
                  title={`${preset.step}. ${preset.name}: ${preset.description}`}
                >
                  <span className="live-step-pip-num">
                    {isDone && !isCurrent ? `✓ Step ${preset.step}` : `Step ${preset.step}`}
                  </span>
                  <span className="live-step-pip-title">{preset.name}</span>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Empty State when visited before starting */}
      {!hasEverRun && !isRunning ? (
        <section className="live-empty-hero">
          <div style={{ fontSize: "36px" }}>⚡</div>
          <h3>Live Mode hasn&apos;t been started this session</h3>
          <p>
            Live Mode runs a deterministic 10-step sequence that simulates real-world payment failures
            including network timeouts, insufficient funds, stolen cards, unstructured bank errors, and safety spend caps.
            Start the run now to watch autonomous triage unfold in real time.
          </p>
          <button
            onClick={() => void handleStart()}
            disabled={liveModeChanging}
            className="primary-button"
            style={{ padding: "10px 24px", fontSize: "14px", fontWeight: "700" }}
          >
            Start Live Mode
          </button>
        </section>
      ) : (
        <>
          {/* Cumulative recovery ticker and time-series chart from earlier tiers (reused) */}
          <RecoveryChart
            summary={funnel.summary}
            loading={funnel.loading}
            error={funnel.error}
            scope="session"
          />

          {/* Recovery Funnel (reused) */}
          <RecoveryFunnel
            summary={funnel.summary}
            loading={funnel.loading}
            error={funnel.error}
            scope="session"
          />

          {/* Large, Single-Column Live Feed */}
          <section className="live-feed-stack" aria-label="Live Decision Feed">
            <div className="live-feed-heading">
              <div>
                <h2>Live Decision Feed</h2>
                <p style={{ margin: "2px 0 0", fontSize: "13px", color: "var(--text-secondary)" }}>
                  Showing each failed payment transaction as it arrives, triaged in real time ({transactions.length} recorded this session).
                </p>
              </div>
              {isRunning && (
                <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#107e54", fontWeight: "700" }}>
                  <span className="pulse-dot" /> LIVE STREAMING
                </div>
              )}
            </div>

            {txError && !transactions.length && (
              <div className="state state-error">Failed to load live feed: {txError}</div>
            )}

            {txLoading && !transactions.length ? (
              <div className="state">Listening for live transactions…</div>
            ) : transactions.length === 0 ? (
              <div className="state">No transactions fired yet. Starting the sequence…</div>
            ) : (
              transactions.map((tx: RecentTransaction, idx: number) => {
                const statusClass =
                  tx.recovery_outcome?.execution_status === "SUCCEEDED"
                    ? "status-succeeded"
                    : tx.recovery_outcome?.execution_status === "HELD" || tx.action === "hold_for_review"
                      ? "status-held"
                      : tx.recovery_outcome?.execution_status === "FAILED"
                        ? "status-failed"
                        : "status-simulated";

                // Step number in reverse (newest is transactions.length - idx)
                const eventNum = transactions.length - idx;

                return (
                  <article key={tx.transaction_id} className={`live-feed-card ${statusClass}`}>
                    {/* Top Row */}
                    <div className="live-card-header">
                      <div className="live-card-meta">
                        <span className="live-card-step-badge">Event #{eventNum}</span>
                        <Link
                          to={`/decisions/${tx.transaction_id}`}
                          className="table-link"
                          style={{ fontSize: "14px", fontWeight: "600" }}
                        >
                          {tx.transaction_id.slice(0, 16)}…
                        </Link>
                        <span style={{ fontSize: "12px", color: "var(--text-tertiary)" }}>
                          {new Date(tx.created_at).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })}
                        </span>
                      </div>

                      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                        <span className="live-card-amount">{money(tx.amount_inr)}</span>
                        <div className="live-card-badges">
                          {tx.path_taken === "deterministic" ? (
                            <span className="badge badge-provider" title="Fast path rule execution">
                              FAST PATH
                            </span>
                          ) : (
                            <span className="badge badge-primary" title="LLM reasoning decision">
                              LLM REASONING
                            </span>
                          )}
                          {tx.was_gated && (
                            <span className="badge badge-error" title="Safety policy gate applied">
                              SAFETY GATED
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Middle Row */}
                    <div className="live-card-body">
                      <div className="live-card-failure-wrap">
                        <span className="live-card-failure-label">Decline Reason</span>
                        <span className="live-card-failure-val">
                          {tx.decline_reason_raw || tx.decline_reason.replace(/_/g, " ").toUpperCase()}
                        </span>
                      </div>

                      <div className="live-card-action-group">
                        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                          <span className="live-card-failure-label">Selected Action</span>
                          <span
                            style={{
                              fontSize: "13px",
                              fontWeight: "700",
                              color: "var(--text-primary)",
                              background: "var(--surface-raised)",
                              padding: "4px 10px",
                              borderRadius: "4px",
                              border: "1px solid var(--border-subtle)",
                            }}
                          >
                            {ACTION_LABELS[tx.action]}
                          </span>
                        </div>

                        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                          <span className="live-card-failure-label">Execution Status</span>
                          <StatusBadge outcome={tx.recovery_outcome} synthetic={tx.is_synthetic} />
                        </div>

                        <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                          <span className="live-card-failure-label">Measured Outcome</span>
                          <OutcomeBadge outcome={tx.recovery_outcome} />
                        </div>
                      </div>
                    </div>

                    {/* Reasoning Snippet Quote */}
                    {tx.reasoning_text && (
                      <div className="live-card-reasoning">
                        <strong>Triage Rationale:</strong>
                        <span>{tx.reasoning_text}</span>
                      </div>
                    )}

                    {/* Footer */}
                    <div className="live-card-footer">
                      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                        {tx.selected_expected_net_recovery_inr != null && (
                          <span>
                            Expected Net:{" "}
                            <strong style={{ color: "var(--text-primary)" }}>
                              {money(tx.selected_expected_net_recovery_inr)}
                            </strong>
                          </span>
                        )}
                        {tx.value_advantage_vs_next_best_inr != null && (
                          <span>
                            Value Advantage:{" "}
                            <strong style={{ color: "#13825f" }}>
                              +{money(tx.value_advantage_vs_next_best_inr)}
                            </strong>
                          </span>
                        )}
                        {tx.confidence != null && (
                          <span>
                            Model Confidence:{" "}
                            <strong style={{ color: "var(--text-primary)" }}>
                              {Math.round(tx.confidence * 100)}%
                            </strong>
                          </span>
                        )}
                      </div>

                      <Link
                        to={`/decisions/${tx.transaction_id}`}
                        className="text-link"
                        style={{ fontSize: "12px", fontWeight: "600" }}
                      >
                        Inspect full decision audit trail →
                      </Link>
                    </div>
                  </article>
                );
              })
            )}
          </section>
        </>
      )}
    </div>
  );
}
