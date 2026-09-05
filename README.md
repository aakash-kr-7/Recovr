# RECOVR

**A payment-failure triage agent for Razorpay's AI Buildathon, Track 3 (Revenue Recovery).**

Not every failed payment is lost money. Some failures are permanent (card
reported lost, account frozen). Many are temporary and fixable (a bank
timeout, an expired session, a card that was momentarily maxed out). Today's
retry tools treat every failure the same way: match the decline code to a
fixed rule, run the rule.

RECOVR reads the decline reason **and the transaction's context**, ranks
permitted actions by expected net recovery, and records each execution and
outcome. Its only provider action is a Razorpay test-mode Payment Link; it is
never called recovered until a later provider outcome confirms it. The
evaluation report is a clearly labeled synthetic, held-out action-economics
comparison — not merchant revenue.

Current limitation: live customer-history retrieval is a documented stub that
returns an empty history. The structured context contract and its synthetic
test coverage exist, but the product must not claim live Razorpay historical
enrichment until that lookup is implemented.

> **Read this first:** [`docs/POSITIONING.md`](docs/POSITIONING.md) is the
> single most important document in this repo. It states plainly what is
> and isn't novel here, names the existing products this overlaps with
> (Razorpay's own smart routing, Slicker, GR4VY, Stripe Smart Retries), and
> explains the actual differentiation: an optional bounded reasoning path for
> ambiguous cases, economic action ranking, and an auditable synthetic
> evaluation. Read that before judging anything else here.

## What's in this repo

| Path | What it is |
|---|---|
| [`backend/`](backend/) | FastAPI service: webhook intake, two-path triage agent (Groq / Claude), economic scoring layer, bounded action executor, audit trail, demo simulator, safe public config, and evaluation harness |
| [`frontend/`](frontend/) | React + TypeScript dashboard: live decision feed, audit trail viewer, recovery report with reliability calibration, settings console, and interactive failure simulator |
| [`docs/`](docs/) | Positioning, architecture, decision log (ADRs), demo validation, and evidence freeze (see below) |
| [`.github/workflows/`](.github/workflows/) | CI: lint + test on every push |

## Key Features

1. **Two-Path Triage Agent**: Fast-path deterministic routing for unambiguous decline reasons; an optional reasoning path (Groq / Anthropic Claude) over structured customer context, timing, and raw decline text.
2. **Economic Decision Engine**: Ranks every permitted action (`retry_same_rail`, `retry_alt_rail`, `escalate_to_dunning`, `hold_for_review`, `no_action`) by expected net recovery value; economics overrides candidate actions when costs/penalties exceed probability gains.
3. **Bounded Action Executor**: Enforces strict allow-listing, per-customer retry limits, and a ₹50,000 batch spend cap. Low-confidence reasoning outputs fail-close to human review.
4. **Interactive Payment Failure Simulator**: Built-in slide-over drawer allowing operators to trigger and inspect realistic failure scenarios (transient UPI timeout, high-value card decline, repeated failure dunning, hard decline block) in real time.
5. **Safe Operational Settings (`GET /config/public`)**: Read-only settings page exposing active operational bounds (LLM provider, models, spend cap, confidence thresholds, credential status, and cost baseline) while strictly excluding all secrets, API keys, and connection strings.
6. **Authentic Design Tokens (Razorpay Blade)**: The UI is styled with authentic Razorpay design tokens (colors, type scale, spacing, border radiuses) mapped into Tailwind classes, including a persistent, calm "TEST MODE" badge. It deliberately carries zero trademarked logos or wordmarks.

## Quick start

See [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md) for full setup. The short version:

```bash
# 1. Backend setup
cd backend
cp .env.example .env        # Configure test-mode keys & LLM provider (Groq default)
python -m venv .venv
# On Windows: .venv\Scripts\activate; On Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Generate synthetic dataset and seed demo database
python scripts/generate_synthetic_data.py
python scripts/seed_demo_database.py

# Launch FastAPI backend
uvicorn app.main:app --reload

# 2. Frontend setup (in a separate terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` for the dashboard, or `http://localhost:8000/docs` for the OpenAPI documentation.

## How it works, in one diagram

```
Payment fails (Razorpay webhook)
        │
        ▼
Confidence gate: is this decline reason unambiguous?
        │
   ┌────┴────┐
   ▼         ▼
Deterministic   Optional LLM reasoning path (Groq / Claude)
fast path       (customer history + timing + decline text)
   │         │
   └────┬────┘
        ▼
Economic scoring engine: ranks options by expected net recovery
        │
        ▼
Bounded action executor (allow-list, ₹50k spend cap, confidence gating)
        │
        ▼
Execute permitted action (Payment Link) → log decision + reasoning + outcome
```

Full detail in [`docs/architecture/overview.md`](docs/architecture/overview.md).

## Evaluation & Calibration

Every evaluation claim is backed by a held-out **synthetic** test set the
system's own tuning never saw. The frozen configuration uses Beta-shrinkage
calibration and structured context; its measured calibration result is
specific to that synthetic evaluation, not a production recovery claim. See [`docs/architecture/failure_log.md`](docs/architecture/failure_log.md#entry-3-empirical-calibration-of-action-probabilities-and-recovery-fractions)
for the full account of how systematic underestimation was diagnosed and
corrected during our honest-iteration process.

Run the evaluation yourself:

```bash
cd backend
python scripts/run_evaluation.py
```

This evaluates selected actions against synthetic hidden counterfactual
outcomes, reports simulated net recovery, regret, and opportunity loss, and
writes the full report to `backend/data/eval/latest_report.json`. The frontend
Evaluation view renders the calibration curve (predicted probability vs.
observed recovery rate) directly from this report. Legacy binary
precision/recall remain secondary diagnostics. See
[`docs/architecture/evaluation.md`](docs/architecture/evaluation.md).

## What broke, and how we got out

Documented honestly, with the real failing case, in
[`docs/architecture/failure_log.md`](docs/architecture/failure_log.md) —
this is a required field on the buildathon application, and we treat it the
same way here: as a real account, not a staged one.

## Project status

Built solo, in one week, for the Razorpay AI Buildathon. The frontend is styled using Razorpay's real published design tokens (extracted from Blade). See
[`docs/decisions/`](docs/decisions/) for the architecture decision records
explaining the calls made along the way (why FastAPI, why the two-path
agent, why Groq provider, why token styling over component package, and why SQLite).

## License

MIT — see [`LICENSE`](LICENSE).

