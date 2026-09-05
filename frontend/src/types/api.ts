export type TriageAction =
  | "retry_same_rail"
  | "retry_alt_rail"
  | "hold_for_review"
  | "escalate_to_dunning"
  | "no_action";
export type TriagePath = "deterministic" | "reasoning";
export type ExecutionStatus =
  "PENDING" | "SUCCEEDED" | "FAILED" | "HELD" | "SIMULATED";
export type ExecutionMode = "REAL_RAZORPAY_ACTION" | "BOUNDED_SIMULATION";

export interface RecoveryOption {
  action: TriageAction;
  estimated_probability: number;
  expected_recovery_inr: number;
  action_cost_inr: number;
  risk_penalty_inr: number;
  expected_net_recovery_inr: number;
  supporting_evidence: string;
}

export interface RecoveryOutcome {
  execution_status: ExecutionStatus;
  actual_recovered_inr: number | null;
  observed_success: boolean | null;
  variance_inr: number | null;
  outcome_timestamp: string;
  provider: string | null;
  provider_reference: string | null;
  mode: ExecutionMode;
  net_recovered_inr: number | null;
  error_code: string | null;
  error_message: string | null;
}

export interface RecentTransaction {
  transaction_id: string;
  amount_inr: number;
  decline_reason: string;
  decline_reason_raw: string;
  is_synthetic: boolean;
  path_taken: TriagePath;
  action: TriageAction;
  reasoning_text: string;
  confidence: number | null;
  was_gated: boolean;
  outcome: string | null;
  created_at: string;
  recovery_options: RecoveryOption[] | null;
  selected_expected_net_recovery_inr: number | null;
  value_advantage_vs_next_best_inr: number | null;
  recovery_outcome: RecoveryOutcome | null;
}

export interface AuditDetail extends RecentTransaction {
  payment_id: string | null;
  failed_at: string;
  customer_id: string;
  customer_history: Record<string, unknown>;
}

export interface PolicyMetrics {
  transaction_count: number;
  total_amount_at_risk_inr: number;
  gross_recovered_inr: number;
  recovery_rate_by_inr: number;
  net_recovery_inr: number;
  true_expected_net_value_inr: number;
  model_expected_net_value_inr: number;
  expected_regret_inr: number;
  realized_regret_inr: number;
  action_distribution: Record<TriageAction, number>;
}

export interface EvaluationReport {
  generated_at: string;
  evaluation_version: string;
  holdout_set_size: number;
  unconstrained: Record<
    "retry_all_same_rail" | "fixed_rule_policy" | "recovr",
    PolicyMetrics
  >;
  constrained: Record<
    "retry_all_same_rail" | "fixed_rule_policy" | "recovr",
    PolicyMetrics
  >;
  evaluation_views: {
    unconstrained_decision_quality: PolicyMetrics;
    constrained_execution_quality: PolicyMetrics;
    cap_induced_execution_overrides: number;
  };
  calibration?: Array<{
    bin: string;
    count: number;
    expected_probability: number;
    observed_recovery_rate: number;
  }>;
  note: string;
}

export interface PublicConfig {
  llm_provider: string;
  batch_spend_cap_inr: number;
  min_auto_execute_confidence: number;
  max_customer_recovery_attempts: number;
  has_real_razorpay_credentials: boolean;
  razorpay_mode: "demo_seeded_data" | "real_test_credentials" | string;
  data_mode_label: string;
  environment: string;
  reasoning_model: string;
  groq_model: string;
  wasted_retry_cost_inr: number;
  alternate_rail_cost_inr: number;
  review_cost_inr: number;
  dunning_cost_inr: number;
}
