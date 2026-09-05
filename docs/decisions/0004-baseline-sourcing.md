# ADR 0004: Sourcing the naive-retry baseline

## Status
Accepted

## Context
The evaluation report (`docs/architecture/evaluation.md`) compares the
triage system's recovery rate against a naive "retry everything" baseline.
For that comparison to mean anything, the baseline recovery rate needs to
be a real, cited figure rather than an invented one.

## Decision
Use the commonly cited 15-20% range for naive subscription/payment retry
recovery, sourced from public figures referenced in Razorpay's and
Stripe's own blog content on payment recovery. Cite the specific source
URL in `backend/app/core/config.py` next to the constant, and restate it
in the evaluation report output so it's never presented as our own
number.

## Reasoning
An uncited number in a rigor-focused submission undermines the entire
positioning in `docs/POSITIONING.md`. If the baseline can't be traced to a
source, don't use it — better to show only the measured numbers (system
vs. ground truth) than to pair a real number with a fabricated
comparison point.

## Consequences
If the cited source is unavailable or the figure can't be re-verified
before submission, the evaluation report should omit the naive-baseline
comparison entirely rather than keep an unsourced number. The measured
system-vs-ground-truth numbers stand on their own.
