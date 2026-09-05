# ADR 0002: No custom-trained ML model

## Status
Accepted

## Context
A payment-failure classifier could, in principle, be a custom-trained
model (e.g., a gradient-boosted classifier on decline features). This is
also the default instinct for a "fraud/risk ML" style submission, and it's
tempting to reach for it to look more technically substantial.

## Decision
Do not train a custom model. Use the Claude API directly for the
reasoning path, with structured context passed in the prompt, and a
deterministic rule table for the fast path.

## Reasoning
- **No real training data exists.** Any model trained this week would be
  trained on the same synthetic data used for evaluation, which makes the
  eval numbers meaningless (the model would be graded on data drawn from
  the same generator it learned from, not truly held-out in spirit even
  if held-out in mechanics).
- **The judging criteria explicitly reward tool choice, including the
  choice not to use one.** A custom model trained on a week of synthetic
  data is not more defensible than a well-scoped prompt — it just looks
  more complicated. Complexity is not the goal; judgment is.
- **Reasoning over unstructured/varied decline text is a better fit for
  an LLM than a classifier.** Decline reason strings are not standardized
  across banks and card networks. A classifier needs a fixed feature
  schema; an LLM can reason about a decline reason it has never seen a
  labeled example of.
- **Time.** Model training, hyperparameter iteration, and overfitting
  checks are a multi-day project on their own. That time is better spent
  on the evaluation harness and the executor's safety bounds, which are
  what the judging bar actually asks for.

## Alternatives considered
- **Fine-tuned small classifier** — rejected per above; the honest
  evaluation story is stronger without it.
- **Rules engine only, no LLM at all** — rejected because it would be a
  strictly worse version of GR4VY with no differentiation at all. The
  reasoning path is what makes the context-divergence claim in
  `docs/POSITIONING.md` true.

## Consequences
The reasoning path's cost and latency scale with the number of ambiguous
cases, not the total transaction volume — which is exactly the point of
the confidence gate in ADR 0003.

### Addendum: Provider-Agnostic LLM Path
We added a free-tier LLM option (Groq with `llama-3.3-70b-versatile`) so the reasoning path doesn't require a paid Anthropic key during development. Groq was chosen for free-tier development because it doesn't require a credit card, is OpenAI-compatible (making tool-calling easy to port), and is fast enough for a live demo. The paid Anthropic integration is kept as a documented upgrade path for submission, and both providers strictly implement the same `ReasoningResult` contract enforced by unit tests.
