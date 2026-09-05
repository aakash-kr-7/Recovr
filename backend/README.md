# RECOVR — backend

FastAPI service implementing the payment-failure triage agent. See
[`docs/architecture/overview.md`](../docs/architecture/overview.md) for the
full design.

## Setup

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with:
- `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` — from your Razorpay **test
  mode** dashboard (Settings → API keys). Never use live keys with this
  project.
- `ANTHROPIC_API_KEY` or configured Groq credentials — for the optional
  reasoning path. A provider failure is handled fail-closed as review.
- `WASTED_RETRY_COST_INR` — leave the default unless you have a better
  sourced figure; see `app/core/config.py` for the citation.

## Generate the synthetic dataset

```bash
python scripts/generate_synthetic_data.py
```

This writes `data/synthetic/transactions.json` (the working set) and
`data/eval/holdout.json` (the held-out 30%, never touched by development).
Re-running this regenerates both — don't do this after you've started
tuning against the working set, or the holdout stops being held out.

## Run the API

```bash
uvicorn app.main:app --reload
```

Interactive OpenAPI docs are available at `http://localhost:8000/docs`.

### Primary Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/webhooks/razorpay` | Intake for incoming `payment.failed` webhooks (verifies HMAC signatures). |
| `GET` | `/transactions/recent` | Live read model for recent triage decisions and execution statuses. |
| `GET` | `/transactions/audit/{id}` | Detailed lifecycle trace, evaluated options, and reasoning text for a transaction. |
| `GET` | `/evaluation/latest` | Synthetic action-economics evaluation report, counterfactual metrics, and calibration curve. |
| `GET` | `/config/public` | Safe operational parameters (active LLM provider, spend cap, thresholds, cost constants). Secrets are strictly excluded. |
| `GET` | `/demo/presets` | Preset failure scenarios for interactive demonstration. |
| `POST` | `/demo/simulate` | Trigger real-time end-to-end payment failure triage with immediate execution outcome. |

## Seed the Demo Database

To populate the local SQLite database with realistic synthetic triage cases across deterministic, reasoning, and gated actions:

```bash
python scripts/seed_demo_database.py
```

## Run the evaluation

```bash
python scripts/run_evaluation.py
```

Writes the synthetic action-economics evaluation report (including probability calibration metrics) to `data/eval/latest_report.json`.

## Run tests

```bash
pytest
```

## Project layout

```
app/
  main.py             FastAPI app instantiation, router mounting
  core/
    config.py         Settings (env-driven), cost constants with citations
    logging.py        Structured logging setup
  api/
    webhooks.py       POST /webhooks/razorpay — payment.failed intake
    transactions.py   GET endpoints the dashboard reads
    evaluation.py     GET endpoint serving the latest eval report
    config.py         GET /config/public — safe operational configuration
    demo.py           GET /demo/presets & POST /demo/simulate
  agent/
    gate.py           Confidence gate: routes to fast path or reasoning path
    reasoning.py      LLM call + prompt assembly for reasoning path (Groq / Claude)
    executor.py       Bounded action executor: allow-list + spend cap + gating
    economics/
      scoring.py      Expected net recovery scoring formula
      probability_heuristics.py Calibrated Beta-shrinkage heuristics
      historical_evidence.py   Historical outcome lookups with holdout isolation
    providers/
      groq_provider.py         Groq OpenAI-compatible provider
      anthropic_provider.py    Anthropic Claude provider
    prompts/
      triage_system_prompt.md
    rules/
      decline_taxonomy.py      Fast-path decision table, documented per entry
  models/
    transaction.py        ORM model for an incoming failed transaction
    audit_entry.py        ORM model for the audit trail
    recovery_decision.py  ORM model for evaluated recovery options and winning choice
    recovery_outcome.py   ORM model for post-execution measured results
  schemas/
    webhook.py            Pydantic schema for Razorpay webhook payloads
    triage.py             Pydantic schema for a triage decision
    recovery.py           Pydantic schemas for RecoveryOption, Context, Decision, Outcome
    config.py             Pydantic schema for PublicConfigResponse
  services/
    razorpay_client.py    Thin wrapper around the Razorpay SDK, test-mode only
    customer_history.py   Customer history retrieval contract
  db/
    session.py            SQLite engine/session setup
    init_db.py            Table creation
  utils/
    money.py              ₹ formatting and cost-calculation helpers
scripts/
  generate_synthetic_data.py   Generates synthetic dataset and holdout partition
  seed_demo_database.py        Seeds local database with realistic demo cases
  run_evaluation.py            Runs multi-policy counterfactual evaluation
  run_llm_ablation.py          Runs LLM vs pure-economics ablation study
data/
  synthetic/          Generated working-set data (gitignored)
  eval/               Holdout data and frozen latest_report.json
tests/
  unit/               Fast-path table, gate, scoring, public config, calibration
  integration/        End-to-end webhook, closed loop, demo lifecycle & simulator
  fixtures/           Shared test fixtures (context_divergence_cases.json)
```

