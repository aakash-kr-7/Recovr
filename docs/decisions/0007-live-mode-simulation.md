# ADR 0007: Live Mode streaming simulation and ordered scenario playback

## Status
Accepted

## Context
During live demonstrations and review sessions, evaluators and operators need to observe RECOVR's two-path triage, economic ranking, safety gating, and outcome reconciliation in real time. However, relying solely on manually generated external Razorpay webhook events during a live demo introduces unpredictable timing, requires public tunneling infrastructure (e.g. ngrok), and does not guarantee that reviewers see the full spectrum of edge cases (such as spend caps, compliance blocks, unmapped bank errors, or night-time timeouts).

We needed an integrated playback mechanism that allows reviewers to watch payment failure triage unfold continuously, while ensuring complete fidelity to the real decision engine.

## Decision
Implement a server-driven Live Mode playback engine (`POST /demo/live-mode/start`, `POST /demo/live-mode/stop`, `GET /demo/live-mode/status`) coupled with a dedicated frontend command console (`/live`):

1. **Deterministic Ordered Playback Script**: Rather than generating random synthetic transactions, Live Mode steps sequentially through an ordered script of 10 canonical scenarios:
   - Nighttime bank timeout
   - High-value clean customer
   - Stolen card
   - Unmapped bank error
   - Repeat offender
   - Low-value nuisance
   - Spend cap in action
   - Genuinely novel bank code
   - Account closed
   - Compliance block

2. **Zero Engine Bypassing**: Live Mode transactions execute through the exact same `_simulate_transaction` pipeline as manual simulations and live webhooks. They pass through the confidence gate (`app/agent/gate.py`), call the LLM reasoning path if ambiguous (`app/agent/reasoning.py`), evaluate economic expected values (`app/agent/economics/scoring.py`), and enforce safety bounds (`app/agent/executor.py`).

3. **Session-Level Metric Isolation**: To prevent streaming demo playback from contaminating historical benchmarks, transactions created during Live Mode carry `data_split='live_mode'`. The frontend funnel summary API (`GET /transactions/funnel-summary?scope=session`) isolates metrics to the active session by default, allowing the dashboard and live view to display pristine, self-consistent numbers.

4. **Honest Metric Accounting**: Transactions currently in `hold_for_review` awaiting human resolution have unobserved success (`observed_success is None`). These cases are strictly excluded from the recovery rate denominator so they are never falsely penalized as failed recoveries.

## Consequences
- Evaluators can launch and pause a full real-time demonstration with a single click in the UI header or on the `/live` page.
- Every scenario produces full, verifiable database records across `transactions`, `recovery_decisions`, `recovery_outcomes`, and `audit_entries`.
- All decisions, reasoning traces, and economic comparisons remain fully inspectable in the Decision Detail and Audit Trail views.
