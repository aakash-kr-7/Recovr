# RECOVR evidence freeze

Frozen for the final Buildathon submission. This document records what the
repository can support as of the current canonical artifacts; it does not
authorize a new evaluation run or a change to the holdout data.

## Canonical synthetic evaluation

| Field | Frozen value |
| --- | --- |
| Label | **SYNTHETIC EVALUATION** |
| Report | `backend/data/eval/latest_report.json` |
| Evaluation version | `comparable_action_economics_v3` |
| Generated | 2026-09-04T15:43:31.025599 |
| Canonical seed | 42 |
| Holdout size | 60 |
| Holdout SHA-256 | `3879489a456579010ed9a64e20459ff70746c862ab21fba052af05eaecb9d7b3` |
| Fairness rule | Every policy sees the same ordered holdout; constrained view applies the same action-cost budget to every policy. |

The primary comparison is action-level economics. Legacy binary retry
diagnostics are secondary and must not be used as the headline result.

| Policy | Amount at risk | Net recovery | Recovery rate | Expected regret | Realized regret | Incremental vs retry-all | Incremental vs fixed rule |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Retry-all | ₹462,701.13 | ₹96,814.50 | 21.10% | ₹43,600.71 | ₹153,268.45 | — | — |
| Fixed-rule | ₹462,701.13 | ₹135,106.44 | 29.30% | ₹24,271.37 | ₹114,976.51 | ₹38,291.94 | — |
| RECOVR | ₹462,701.13 | ₹156,183.86 | 33.86% | ₹10,952.35 | ₹93,899.09 | ₹59,369.36 | ₹21,077.42 |

All INR values in this table are counterfactual synthetic-evaluation values,
not actual merchant recovery.

## Five-seed robustness

Seeds: `42, 7, 19, 73, 101`.

| Policy | Mean net recovery | Std. dev. | Mean expected regret | Mean recovery rate |
| --- | ---: | ---: | ---: | ---: |
| Retry-all | ₹94,164.80 | ₹11,914.28 | ₹48,001.90 | 21.32% |
| Fixed-rule | ₹105,752.61 | ₹21,991.55 | ₹29,881.72 | 23.70% |
| RECOVR | ₹139,695.12 | ₹42,844.39 | ₹6,694.05 | 31.14% |

RECOVR is the synthetic net-recovery winner in four of five seeds; seed 19
is won by Retry-all. Do not claim it wins every seed.

## Frozen decision configuration

| Component | Frozen configuration |
| --- | --- |
| Probability calibration | Empirical-Bayes/Beta shrinkage with W=10 pseudo-observations, structural zeros, and additive context modifiers in `app/agent/economics/probability_heuristics.py`. |
| Economic formula | `probability × amount × recovery_fraction − action_cost − risk_penalty`. |
| Recovery fractions | same-rail 1.00; alternate rail 1.00; hold 0.90; dunning 0.82; no action 0.00. |
| Action costs | same-rail ₹8; alternate rail ₹10; hold ₹6; dunning ₹4; no action ₹0. |
| Risk penalties | Retry actions: +₹50 for compliance/lost-card patterns, +₹5 for low prior-success history, +₹15 for same-rail expired-card retry; other actions ₹0. |
| LLM boundary | Optional structured contextual signals; they cannot set probabilities directly or authorize execution. Economics and safety are authoritative. |

The repository does not persist a separate model-version ID or immutable
configuration hash beyond the report version and source configuration above.
This is a reproducibility limitation, not a reason to infer another version.

## Evidence classification

| Classification | Verified evidence |
| --- | --- |
| **REAL VERIFIED** | Razorpay webhook signature verification; a real test-mode Payment Link API request attempt; Razorpay's authentication response; transaction/decision/outcome/audit persistence; frontend lifecycle rendering. |
| **MOCK VERIFIED** | Payment Link paid and expired callback handling; successful outcome persistence; duplicate callback handling; historical-evidence retrieval and holdout exclusion. |
| **SYNTHETIC EVALUATION** | Recovered INR, counterfactual action outcomes, policy baselines, regret, recovery rates, calibration metrics, and five-seed robustness. |
| **UNVERIFIED** | A real successful Payment Link recovery; real recovered merchant INR; an LLM-caused economic lift. |

## Final golden demo

Use the documented failure-path record in
[`DEMO_VALIDATION.md`](DEMO_VALIDATION.md):
`4f82652a-749b-4e10-a821-482077400b3b`.

1. Signed `payment.failed`, ₹100, lost-card decline.
2. Empty customer history; deterministic fast path.
3. LLM not invoked; dunning has the highest expected net (₹26.75).
4. Safety passes the permitted dunning action.
5. Execution mode is `REAL_RAZORPAY_ACTION`; Razorpay responds
   `Authentication failed`.
6. Outcome is `FAILED`, actual recovery and provider reference are null, and
   audit outcome is `execution_failed`.
7. The UI shows `REAL · RAZORPAY` and `EXECUTION FAILED`, never recovered.
