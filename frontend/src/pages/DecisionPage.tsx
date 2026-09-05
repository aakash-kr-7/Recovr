import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { OutcomeBadge, StatusBadge } from "@/components/StatusBadges";
import { ACTION_LABELS, money, percent } from "@/lib/operations";
import type { AuditDetail } from "@/types/api";
import { PageHeader } from "@/components/PageHeader";
import { PageContext } from "@/components/PageContext";

export function DecisionPage() {
  const { transactionId } = useParams();
  const navigate = useNavigate();
  const [detail, setDetail] = useState<AuditDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!transactionId) return;
    api
      .getAuditDetail(transactionId)
      .then(setDetail)
      .catch((err: unknown) =>
        setError(
          err instanceof Error ? err.message : "Unable to load decision",
        ),
      );
  }, [transactionId]);

  if (error)
    return (
      <div className="page-stack">
        <div className="state state-error">{error}</div>
      </div>
    );
  if (!detail)
    return (
      <div className="page-stack">
        <div className="state">Loading transaction lifecycle…</div>
      </div>
    );

  const customerHistory = detail.customer_history ?? {};
  const historyEntries = Object.entries(customerHistory);

  return (
    <div className="page-stack">
      <PageHeader
        backLink={
          <button
            onClick={() => {
              if (window.history.length > 1) {
                navigate(-1);
              } else {
                navigate("/recoveries");
              }
            }}
            className="back-link cursor-pointer bg-transparent border-none text-brand font-medium inline-flex items-center gap-1 p-0 hover:underline"
            type="button"
          >
            ← Back to worklist
          </button>
        }
        eyebrow="TRANSACTION LIFECYCLE · DECISION DETAIL"
        title="Payment decision inspection"
        description={`Transaction ${detail.transaction_id}`}
      >
        <div className="flex items-center gap-2">
          {detail.is_synthetic && <span className="demo-label">DEMO DATA</span>}
          <StatusBadge
            outcome={detail.recovery_outcome}
            synthetic={detail.is_synthetic}
          />
          <OutcomeBadge outcome={detail.recovery_outcome} />
        </div>
      </PageHeader>

      <div className="detail-grid">
        {/* Payment & Failure Diagnostics */}
        <section className="panel">
          <h2>Payment & failure diagnostics</h2>
          <dl className="definition-list">
            <div>
              <dt>Transaction ID</dt>
              <dd className="font-mono text-75">{detail.transaction_id}</dd>
            </div>
            <div>
              <dt>Payment ID</dt>
              <dd className="font-mono text-75">{detail.payment_id ?? "Unavailable"}</dd>
            </div>
            <div>
              <dt>Amount at risk</dt>
              <dd><strong>{money(detail.amount_inr)}</strong></dd>
            </div>
            <div>
              <dt>Normalized decline reason</dt>
              <dd>
                <code className="font-mono text-75 font-semibold text-slate-800 bg-slate-100 px-1.5 py-0.5 rounded-2xsmall">
                  {detail.decline_reason}
                </code>
              </dd>
            </div>
            <div>
              <dt>Raw decline text</dt>
              <dd className="text-slate-600 italic">
                "{detail.decline_reason_raw || detail.decline_reason}"
              </dd>
            </div>
            <div>
              <dt>Failed timestamp</dt>
              <dd>{new Date(detail.failed_at).toLocaleString()}</dd>
            </div>
          </dl>
        </section>

        {/* Customer History Used */}
        <section className="panel">
          <h2>Customer history & context</h2>
          <dl className="definition-list">
            <div>
              <dt>Customer ID</dt>
              <dd className="font-mono text-75">{detail.customer_id}</dd>
            </div>
            {historyEntries.length > 0 ? (
              historyEntries.map(([key, val]) => {
                let formattedVal = String(val);
                let label = key.replace(/_/g, " ");
                if (key === "prior_success_rate" && typeof val === "number") {
                  formattedVal = percent(val);
                  label = "Prior success rate";
                } else if (key === "prior_transaction_count") {
                  label = "Prior transactions";
                  formattedVal = `${val} attempts`;
                } else if (key === "account_age_days") {
                  label = "Account age";
                  formattedVal = `${val} days`;
                } else if (key === "most_recent_decline_reason") {
                  label = "Most recent decline";
                }
                return (
                  <div key={key}>
                    <dt className="capitalize">{label}</dt>
                    <dd>{formattedVal}</dd>
                  </div>
                );
              })
            ) : (
              <div>
                <dt>History</dt>
                <dd>No historical transactions on record for this customer.</dd>
              </div>
            )}
          </dl>
        </section>
      </div>

      {/* Candidate Recovery Options Comparison (EVERY Option) */}
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Candidate recovery options comparison</h2>
            <p>
              Every evaluated action scored by economic expected value net of cost and risk.
              Authoritative ranking produced by RECOVR engine.
            </p>
          </div>
          {detail.value_advantage_vs_next_best_inr != null && detail.value_advantage_vs_next_best_inr > 0 && (
            <span className="badge badge-positive">
              +{money(detail.value_advantage_vs_next_best_inr)} net advantage vs next-best
            </span>
          )}
        </div>

        {detail.recovery_options && detail.recovery_options.length > 0 ? (
          <div className="table-scroll">
            <table className="operations-table">
              <thead>
                <tr>
                  <th>Action candidate</th>
                  <th>Estimated probability</th>
                  <th>Expected gross</th>
                  <th>Action cost</th>
                  <th>Risk penalty</th>
                  <th>Expected net recovery</th>
                  <th>Supporting evidence & rationale</th>
                </tr>
              </thead>
              <tbody>
                {[...detail.recovery_options]
                  .sort(
                    (a, b) =>
                      b.expected_net_recovery_inr - a.expected_net_recovery_inr,
                  )
                  .map((option) => {
                    const isSelected = option.action === detail.action;
                    return (
                      <tr
                        key={option.action}
                        className={isSelected ? "selected-row" : ""}
                      >
                        <td>
                          <strong>{ACTION_LABELS[option.action]}</strong>{" "}
                          {isSelected && (
                            <span className="badge badge-positive ml-1">
                              SELECTED WINNER
                            </span>
                          )}
                        </td>
                        <td>{percent(option.estimated_probability)}</td>
                        <td>{money(option.expected_recovery_inr)}</td>
                        <td>{money(option.action_cost_inr)}</td>
                        <td>{money(option.risk_penalty_inr)}</td>
                        <td>
                          <strong className={isSelected ? "text-brand" : ""}>
                            {money(option.expected_net_recovery_inr)}
                          </strong>
                        </td>
                        <td className="text-slate-600 max-w-xs whitespace-normal text-75">
                          {option.supporting_evidence || "No additional notes"}
                        </td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="state">
            Economic candidate options ranking unavailable for this transaction.
          </div>
        )}
      </section>

      {/* Decision Rationale, Safety Gate & AI Reasoning */}
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>RECOVR decision rationale & safety gate</h2>
            <p>Contextual reasoning informs. Economic scoring decides. Safety boundaries enforce.</p>
          </div>
          <span className="badge badge-neutral">
            {detail.path_taken.toUpperCase()} PATH
          </span>
        </div>

        <div className="reasoning-grid">
          <div>
            <p className="eyebrow">SELECTED ACTION & REASONING</p>
            <p className="font-medium text-slate-900 mb-1">
              Selected: <strong>{ACTION_LABELS[detail.action]}</strong>
            </p>
            <p className="text-slate-700 leading-relaxed bg-surface-subtle p-3 rounded border border-border-subtle">
              "{detail.reasoning_text}"
            </p>
          </div>
          <div>
            <p className="eyebrow">ECONOMIC SELECTION</p>
            <p>
              Selected <strong>{ACTION_LABELS[detail.action]}</strong> with expected net recovery of{" "}
              <strong>{money(detail.selected_expected_net_recovery_inr)}</strong>.
            </p>
            {detail.value_advantage_vs_next_best_inr != null && (
              <p className="mt-2 text-slate-600">
                Delivers <strong>{money(detail.value_advantage_vs_next_best_inr)}</strong> greater expected net revenue than the second-best candidate action.
              </p>
            )}
          </div>
          <div>
            <p className="eyebrow">SAFETY GATE & EXECUTION BOUNDS</p>
            <p>
              Gate status:{" "}
              {detail.was_gated ? (
                <span className="badge badge-sim">HELD BY CONFIDENCE GATE</span>
              ) : (
                <span className="badge badge-positive">PASSED CONFIDENCE GATE</span>
              )}
            </p>
            <p className="mt-2 text-slate-600">
              Confidence score:{" "}
              <strong>{detail.confidence != null ? percent(detail.confidence) : "Deterministic / Unscored"}</strong>
            </p>
            <p className="mt-1 text-slate-500 text-75">
              {detail.was_gated
                ? "Low confidence or safety policy routed this case to review."
                : "Confidence passed minimum threshold. Bounded execution permitted."}
            </p>
          </div>
        </div>

        <ol className="timeline mt-6">
          <li>
            <strong>1. Failure detected</strong>
            <span>{detail.decline_reason} ("{detail.decline_reason_raw}")</span>
          </li>
          <li>
            <strong>2. Customer context evaluated</strong>
            <span>
              {historyEntries.length > 0
                ? `${historyEntries.length} profile factors checked`
                : "Customer profile evaluated"}
            </span>
          </li>
          <li>
            <strong>3. Economic candidate scoring</strong>
            <span>
              {detail.recovery_options?.length ?? 0} candidate recovery actions evaluated
            </span>
          </li>
          <li>
            <strong>4. Safety check</strong>
            <span>
              {detail.was_gated
                ? "Held by confidence gate — routed to review"
                : "Passed safety checks"}
            </span>
          </li>
          <li>
            <strong>5. Selected action</strong>
            <span>{ACTION_LABELS[detail.action]}</span>
          </li>
          <li>
            <strong>6. Execution & outcome</strong>
            <span>
              {detail.recovery_outcome?.execution_status ?? "Outcome pending"}
            </span>
          </li>
        </ol>
      </section>

      {/* Execution Result & Outcome */}
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Execution result & resolved outcome</h2>
            <p>Verified provider execution and measured recovery outcomes.</p>
          </div>
          <div className="flex items-center gap-2">
            <OutcomeBadge outcome={detail.recovery_outcome} />
            <StatusBadge
              outcome={detail.recovery_outcome}
              synthetic={detail.is_synthetic}
            />
          </div>
        </div>

        <dl className="definition-list">
          <div>
            <dt>Execution status</dt>
            <dd>
              <strong>{detail.recovery_outcome?.execution_status ?? "PENDING"}</strong>
            </dd>
          </div>
          <div>
            <dt>Execution mode</dt>
            <dd>
              {detail.recovery_outcome?.mode === "REAL_RAZORPAY_ACTION" ? (
                <span className="badge badge-provider">REAL RAZORPAY TEST-MODE</span>
              ) : (
                <span className="badge badge-sim">BOUNDED SIMULATION</span>
              )}
            </dd>
          </div>
          <div>
            <dt>Actual recovered</dt>
            <dd className="font-semibold text-positive">
              {money(detail.recovery_outcome?.actual_recovered_inr)}
            </dd>
          </div>
          <div>
            <dt>Expected net</dt>
            <dd>{money(detail.selected_expected_net_recovery_inr)}</dd>
          </div>
          <div>
            <dt>Net recovered</dt>
            <dd>{money(detail.recovery_outcome?.net_recovered_inr)}</dd>
          </div>
          <div>
            <dt>Outcome variance</dt>
            <dd>{money(detail.recovery_outcome?.variance_inr)}</dd>
          </div>
          <div>
            <dt>Observed success</dt>
            <dd>
              {detail.recovery_outcome?.observed_success === true
                ? "Recovered successfully"
                : detail.recovery_outcome?.observed_success === false
                ? "Unsuccessful recovery"
                : "Pending / Unobserved"}
            </dd>
          </div>
          <div>
            <dt>Provider reference</dt>
            <dd className="font-mono text-75">
              {detail.recovery_outcome?.provider_reference ?? "Unavailable"}
            </dd>
          </div>
          {detail.recovery_outcome?.error_code && (
            <div>
              <dt>Error code</dt>
              <dd className="text-negative font-mono text-75">
                {detail.recovery_outcome.error_code}
              </dd>
            </div>
          )}
          {detail.recovery_outcome?.error_message && (
            <div>
              <dt>Error message</dt>
              <dd className="text-negative text-75">
                {detail.recovery_outcome.error_message}
              </dd>
            </div>
          )}
          <div>
            <dt>Outcome timestamp</dt>
            <dd>
              {detail.recovery_outcome?.outcome_timestamp
                ? new Date(detail.recovery_outcome.outcome_timestamp).toLocaleString()
                : "Pending"}
            </dd>
          </div>
        </dl>
      </section>

      <PageContext>
        This view exposes the complete transparent decision trail for a single failed payment — comparing expected economic value across all candidate actions, showing verbatim LLM reasoning, and recording the eventual recovery outcome.
      </PageContext>
    </div>
  );
}
