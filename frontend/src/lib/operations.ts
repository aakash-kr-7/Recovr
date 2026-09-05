import type { RecoveryOutcome, TriageAction } from "@/types/api";

export const ACTION_LABELS: Record<TriageAction, string> = { retry_same_rail: "Retry", retry_alt_rail: "Alternate rail", hold_for_review: "Review", escalate_to_dunning: "Dunning", no_action: "No action" };
export function money(value: number | null | undefined): string { return value === null || value === undefined ? "Unavailable" : `₹${value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`; }
export function percent(value: number | null | undefined): string { return value === null || value === undefined ? "Unavailable" : `${(value * 100).toFixed(1)}%`; }
export function executionBadge(outcome: RecoveryOutcome | null, synthetic: boolean): { label: string; className: string } { if (outcome?.mode === "REAL_RAZORPAY_ACTION") return { label: "REAL · RAZORPAY", className: "badge-provider" }; if (synthetic || outcome?.mode === "BOUNDED_SIMULATION") return { label: "SIMULATED · TEST HARNESS", className: "badge-sim" }; return { label: "INTERNAL · REVIEW", className: "badge-neutral" }; }
export function outcomeBadge(outcome: RecoveryOutcome | null): { label: string; className: string } {
  const status = outcome?.execution_status.toUpperCase();
  if (!outcome || status === "PENDING") return { label: "PENDING", className: "badge-neutral" };
  if (status === "FAILED" || status === "FAILED_TO_EXECUTE") return { label: "EXECUTION FAILED", className: "badge-error" };
  if (status === "HELD" || status === "SKIPPED") return { label: "HELD", className: "badge-neutral" };
  if (status === "SIMULATED") return { label: "SIMULATED", className: "badge-sim" };
  if (outcome.actual_recovered_inr !== null && outcome.actual_recovered_inr > 0) return { label: "RECOVERED", className: "badge-positive" };
  if (outcome.observed_success === false) return { label: "NOT RECOVERED", className: "badge-negative" };
  return { label: "RECOVERING", className: "badge-neutral" };
}
