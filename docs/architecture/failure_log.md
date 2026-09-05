# What broke, and how we got out

The buildathon application asks for this directly, and reads it first
alongside "what it solves." So this is a real account, filled in as things
actually happen during the build — not a staged scenario written after the
fact to look good on camera.

## Format

Each entry: what broke, what the system did as a result, what the gate or
bound caught (if anything), and what was changed afterward. Entries are
added chronologically as the build progresses; nothing is deleted or
smoothed over after the fact.

---

### Entry template (fill in as real failures happen)

**Date:**
**What broke:**
**What the system did:**
**What caught it (gate / spend cap / test):**
**What we changed:**
**Would this still happen today:**

---

### Entry 1: labeler/rule-table disagreement found during scaffolding verification

**Date:** 2026-09-04 (during initial repo scaffolding, before Day 1 of the build week)
**What broke:** The synthetic data generator's ground-truth labeler
(`assign_ground_truth` in `scripts/generate_synthetic_data.py`) assigned
`escalate_to_dunning` to an entire bucket of decline codes
(`card_reported_lost_or_stolen`, `account_closed`, `invalid_card_number`,
`compliance_block`) as a shortcut, except for a single carved-out
exception. The deterministic fast-path rule table
(`app/agent/rules/decline_taxonomy.py`) — written separately, with a
documented reason per entry — actually assigns three *different* actions
across that same set: `escalate_to_dunning`, `no_action`, and
`hold_for_review`. Running the fast path against real generated holdout
data surfaced 6 of 17 deterministic-path cases disagreeing with their own
ground truth.
**What the system did:** Executed exactly as the rule table specifies —
this was correct behavior. The bug was entirely in the labeler being a
less careful piece of logic than the production rule table it was meant
to grade.
**What caught it:** Not a gate or a spend cap — this was caught by
actually running the generator's output through the real gate and
executor end to end and comparing predicted vs. ground truth by hand,
rather than trusting that both pieces of code agreed just because they
were written around the same time.
**What we changed:** Rewrote `assign_ground_truth` to assign each decline
code's ground-truth action individually, matching the specific reasoning
already documented per entry in `decline_taxonomy.py`, instead of bucketing
several codes under one shortcut label.
**Would this still happen today:** No — verified with a full re-run
against the regenerated holdout set: 0 mismatches on the deterministic
path after the fix.

This is left in as a real account, including the fact that it was found
before Day 1 rather than during the live build week — the lesson (the
labeler and the system under test must be checked against each other, not
assumed to agree) applies regardless of when it was found, and honesty
about the timeline matters more than making it look like it happened at a
more dramatic moment.

---

## Notes for use during the build

- The most valuable entry here is a genuine miss caught during evaluation
  — e.g., the reasoning path confidently picking `retry_alt_rail` for a
  case the ground truth says was a hard decline, and the low-confidence
  gate routing it to `hold_for_review` instead of letting it execute. If
  this happens during a real `run_evaluation.py` run, capture the exact
  transaction ID, the reasoning text the model produced, and what the gate
  did. That is far stronger evidence for the pitch video than any
  invented scenario.
- If a genuine integration failure happens against the real Razorpay
  test-mode API (a malformed webhook payload, an auth error, a rate limit),
  log it here too — "what broke" doesn't only mean the agent's reasoning.
- Do not backfill this file with a polished, low-stakes fake failure the
  night before submission. A judge who has read a few dozen of these can
  tell the difference, and an honest miss is a stronger signal than a
  manufactured one.

---

### Entry 2: Systematic under-estimation of recovery probability

> **Evidence scope:** Every amount, probability, and outcome in Entries 2
> and 3 is from the canonical synthetic evaluation or its synthetic training
> data. None is a real merchant recovery result.

> **[SUPERSEDED — 2026-09-04]:** This entry has been superseded by Entry 3 below. The initial hypothesis that this gap was merely "probabilistic estimates vs. deterministic binary ground truth self-correcting via the historical evidence loop" was incorrect; by design, the historical evidence loop is strictly forbidden from querying holdout data, so it could never have resolved a holdout miscalibration. See Entry 3 for the true root-cause analysis, Beta-shrinkage recalibration, and recovery fraction fix.

**Date:** 2026-09-04
**What broke:** The economic scoring layer massively under-estimated recovery amounts during the holdout evaluation. For example, on transaction `1c0e727e-8888-4d0a-a4ce-0e16c3859424` (`insufficient_funds`, ₹14,781.26), the system estimated a 13% probability of success and expected a recovery of ₹1,915.65. The actual recovered amount was the full ₹14,781.26. Across the whole holdout set, the system expected ₹100,515 but actually recovered ₹309,117.
**What the system did:** It still correctly selected `retry_same_rail` because even the low expected value (₹1,915) outweighed the wasted retry cost (₹8). So it made the right decision despite the miscalibrated probability.
**What caught it (gate / spend cap / test):** The new economic evaluation metrics in `run_evaluation.py` explicitly computed the expected vs actual variance (₹208,602 total divergence) and output it in the report, making the miscalibration immediately visible.
**What we changed:** Nothing yet — we kept the heuristic as-is because this is an artifact of testing probabilistic heuristics against a deterministic synthetic ground truth (where a "correct" retry equals 100% recovery). The real fix is feeding live historical data into the `historical_evidence` module so estimates reflect observed reality, not static conservative guesses.
**Would this still happen today:** Yes, until the historical evidence loop has enough real data to override the conservative base heuristics.

---

### Entry 3: Empirical calibration of action probabilities and recovery fractions

**Date:** 2026-09-04
**What broke:** Two interconnected modeling defects distorted economic triage:
1. *Systematic Probability Underestimation & Multiplicative Drift:* In `probability_heuristics.py`, base recovery probabilities were arbitrarily depressed (e.g., alternate-rail retry for insufficient funds was 0.05 vs. 0.22 true conditional probability; dunning on expired cards was 0.25 vs. ~0.55 true resolution). Compounding multipliers (such as penalizing accounts under 30 days by up to 30%, despite newer accounts exhibiting higher empirical recovery) drove probability mean errors of -10.36 pp on `retry_alt_rail` and -7.66 pp on `escalate_to_dunning`.
2. *Unadjusted Recovery Fractions:* In `scoring.py`, expected recovery assumed `expected_recovery_inr = probability * amount` for all actions uniformly. However, in the simulated/observed world, manual review recovers ~90% and dunning recovers ~82% of the principal upon success. The scorer systematically overvalued dunning and review relative to direct retries, generating 2 holdout failures classified as `B_cost_or_risk_assumption`.

The earlier note in Entry 2 claiming this would "self-correct via the historical evidence loop" was incorrect: by strict anti-leakage architectural design, the historical evidence lookup queries only the development partition (`data_split != 'holdout'`) and never touches holdout data. The gap was a genuine modeling miscalibration, not an artifact of evaluation.

**What the system did:** Systematically undervalued automated retries and overvalued manual review/dunning, causing 15 primary decision failures attributed to `A_probability_estimate` and 2 failures attributed to `B_cost_or_risk_assumption` in the holdout diagnostic.
**What caught it (gate / spend cap / test):** 
1. Direct calibration analysis on the 140 training transactions via `backend/scripts/analyze_training_calibration.py`, which revealed severe probability bias and Brier score inflation.
2. Error decomposition in `backend/scripts/diagnose_action_evaluation.py`, which isolated counterfactual probability vs. cost/risk attribution on holdout failures.
**What we changed:**
1. *Beta-Shrinkage Calibration with Structural Zeros:* Recalibrated `probability_heuristics.py` using empirical Bayes shrinkage ($W=10$ pseudo-observations toward category priors) on training decline-code base rates, pinned deterministic structural zeros for impossible actions (e.g., same-rail retry on expired cards or compliance blocks), and replaced compounding multipliers with additive contextual shifts while removing the artificial account-age penalty. Validated via 5-fold cross-validation on training data.
2. *Empirically Sourced Recovery Fractions:* Introduced `_RECOVERY_FRACTION` in `scoring.py` (1.00 for `retry_same_rail` and `retry_alt_rail`, 0.90 for `hold_for_review`, 0.82 for `escalate_to_dunning`, sourced from the 140 training transactions) and updated expected recovery to `probability * amount * recovery_fraction`.
3. *Unit Testing:* Added regression test in `tests/unit/test_economics_scoring.py` proving that equal-probability actions produce different expected net values and flip rankings under different recovery fractions.
**Would this still happen today:** No:
- Held-out probability MAE improved from 8.01 pp to 5.23 pp (-34.7%) on `retry_same_rail`, from 10.74 pp to 5.96 pp (-44.5%) on `retry_alt_rail`, and from 7.86 pp to 4.52 pp (-42.5%) on `escalate_to_dunning` (with `hold_for_review` regressing from 3.66 pp to 5.70 pp [+55.7%], yielding a macro-average improvement of 7.57 pp to 5.35 pp [-29.3%]).
- `B_cost_or_risk_assumption` failures dropped from 2 to 0 (eliminated).
- `A_probability_estimate` decision failures dropped by 33% (from 15 to 10).
- Spearman expected rank agreement rose from 0.7650 to 0.8000.
- Unconstrained **synthetic** net recovery increased from ₹144,315.50 to ₹156,183.86 (+₹11,868.36 / +8.2%), and synthetic realized regret decreased from ₹105,767.45 to ₹93,899.09 (-11.2%).

---

### Entry 4: Razorpay test-mode authentication failure retained as an outcome

**Date:** 2026-09-05
**What broke:** A controlled, signed test-mode `payment.failed` webhook for a
₹100 lost-card case correctly reached the supported Payment Link executor,
but Razorpay rejected the configured credential with `Authentication failed`.
No Payment Link ID was created.
**What the system did:** Persisted the decision and failed execution rather
than treating request creation as recovery: `REAL_RAZORPAY_ACTION`,
`FAILED`, `razorpay_request_failed`, null actual recovery, and audit outcome
`execution_failed`.
**What caught it (gate / spend cap / test):** The live webhook-to-provider
run and the decision-detail UI. Duplicate delivery returned `duplicate`; the
frontend initially exposed an uppercase-status contract mismatch, which was
corrected and covered by explicit TypeScript status values.
**What we changed:** No recovery logic or provider behavior. We corrected the
read-model status mapping so `FAILED` renders as `EXECUTION FAILED`.
**Would this still happen today:** Yes until valid Razorpay test credentials
and a publicly reachable webhook endpoint are available. This is an external
environment blocker, not evidence of successful Razorpay recovery.
