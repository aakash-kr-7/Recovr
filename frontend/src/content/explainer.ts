/**
 * Shared explainer content for how RECOVR works.
 *
 * Reused across the About & Configuration page and the Dashboard
 * to ensure a single, consistent, plain-English explanation of the triage pipeline.
 */

export interface PipelineStep {
  step: number;
  label: string;
  title: string;
  description: string;
}

export const HOW_RECOVR_WORKS_TITLE = "How RECOVR works";

export const HOW_RECOVR_WORKS_SENTENCES: readonly string[] = [
  "When a customer payment fails, RECOVR immediately triages the failure to determine the safest and highest-yield recovery path.",
  "The system first checks if the decline reason is unambiguous for instant rule-based handling (the fast path) or requires nuanced context (the LLM reasoning path).",
  "Next, the engine evaluates every permitted recovery action and scores each by its expected net rupee value after deducting rail and operational costs.",
  "Before anything executes, a bounded executor strictly enforces safety limits including batch spend ceilings, per-customer attempt caps, and confidence thresholds.",
  "Every decision is permanently logged with its full reasoning trace and financial projections for complete operational auditability.",
];

export const HOW_RECOVR_WORKS_SUMMARY = HOW_RECOVR_WORKS_SENTENCES.join(" ");

export const HOW_RECOVR_WORKS_STEPS: readonly PipelineStep[] = [
  {
    step: 1,
    label: "Payment Ingestion",
    title: "Payment failure detected",
    description:
      "A failed gateway payment is ingested with customer history and decline metadata.",
  },
  {
    step: 2,
    label: "Routing Check",
    title: "Fast path vs. LLM reasoning",
    description:
      "Unambiguous errors resolve instantly; contextual or nuanced declines route to LLM reasoning.",
  },
  {
    step: 3,
    label: "Economic Scoring",
    title: "Expected net rupee value",
    description:
      "Permitted recovery actions are scored by gross probability minus rail costs and penalties.",
  },
  {
    step: 4,
    label: "Bounded Execution",
    title: "Safety guardrails enforced",
    description:
      "Spend ceilings, attempt caps, and confidence thresholds gate automatic execution.",
  },
  {
    step: 5,
    label: "Auditable Record",
    title: "Full reasoning trace logged",
    description:
      "Every decision and counterfactual score is immutably stored for audit and review.",
  },
];

export const HOW_RECOVR_WORKS = {
  title: HOW_RECOVR_WORKS_TITLE,
  summary: HOW_RECOVR_WORKS_SUMMARY,
  sentences: HOW_RECOVR_WORKS_SENTENCES,
  steps: HOW_RECOVR_WORKS_STEPS,
} as const;
