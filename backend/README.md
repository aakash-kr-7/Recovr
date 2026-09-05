# RECOVR — Backend

FastAPI service implementing the payment-failure triage agent for Razorpay's AI Buildathon. See [`docs/architecture/overview.md`](../docs/architecture/overview.md) for the full architecture design.

---

## Setup

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Fill in `.env` with:
- `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` — from your Razorpay **test mode** dashboard (Settings → API keys). Never use live keys with this project.
- `RAZORPAY_WEBHOOK_SECRET` — secret string for validating incoming webhook signatures.
- `GROQ_API_KEY` or `ANTHROPIC_API_KEY` — for the optional reasoning path (Groq is default; provider failure fails closed to `hold_for_review`).
- `LLM_PROVIDER` — `"groq"` (default) or `"anthropic"`.
- `WASTED_RETRY_COST_INR` — default ₹8.00; see `app/core/config.py` for full citations and cost constants.

---

## Generate Synthetic Dataset & Seed Database

```bash
# 1. Generate working and holdout datasets
python scripts/generate_synthetic_data.py

# 2. Seed the local SQLite database with realistic demo cases
python scripts/seed_demo_database.py
```

`generate_synthetic_data.py` writes `data/synthetic/transactions.json` (the 70% development set) and `data/eval/holdout.json` (the 30% held-out evaluation partition, never touched during development).

---

## Run the API

```bash
uvicorn app.main:app --reload
```

Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

---

## Primary Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/webhooks/razorpay` | Intake for incoming `payment.failed` webhooks (verifies HMAC signatures). |
| `GET` | `/transactions/recent` | Live read model for recent triage decisions and execution statuses. |
| `GET` | `/transactions/funnel-summary` | Aggregated failure/recovery funnel metrics (`session` or `all` scope) with honest pending review exclusions. |
| `GET` | `/transactions/audit/{id}` | Detailed lifecycle trace, evaluated options, and reasoning text for a transaction. |
| `GET` | `/evaluation/latest` | Synthetic action-economics evaluation report, counterfactual metrics, and calibration curve. |
| `GET` | `/config/public` | Safe operational parameters (active LLM provider, spend cap, thresholds, cost constants). Secrets are strictly excluded. |
| `GET` | `/demo/presets` | Preset failure scenarios for interactive demonstration. |
| `POST` | `/demo/simulate` | Trigger real-time end-to-end payment failure triage with immediate execution outcome. |
| `POST` | `/demo/live-mode/start` | Start the automated streaming playback loop of canonical failure scenarios. |
| `POST` | `/demo/live-mode/stop` | Stop / pause the active live-mode streaming loop. |
| `GET` | `/demo/live-mode/status` | Current playback state, sequence progress, and active scenario. |
| `GET` | `/health` | Service health check. |

---

## Run Evaluation & Ablation

```bash
# Run multi-policy counterfactual evaluation against holdout partition
python scripts/run_evaluation.py

# Run LLM vs pure-economics ablation study
python scripts/run_llm_ablation.py

# Analyze training calibration and error decomposition
python scripts/analyze_training_calibration.py
python scripts/diagnose_action_evaluation.py
```

`run_evaluation.py` evaluates selected actions against synthetic hidden counterfactual outcomes, calculates simulated net recovery, regret, and opportunity loss, and writes the full report to `data/eval/latest_report.json`.

---

## Run Tests

```bash
pytest
```

---

## Project Layout

```
backend/
├── app/
│   ├── main.py                     FastAPI app instantiation, CORS, router mounting
│   ├── core/
│   │   ├── config.py               Settings (pydantic-settings), cost constants with citations
│   │   └── logging.py              Structured logging setup
│   ├── api/
│   │   ├── webhooks.py             POST /webhooks/razorpay — payment.failed intake
│   │   ├── transactions.py         GET /recent, /audit/{id}, /funnel-summary
│   │   ├── evaluation.py           GET /evaluation/latest — eval report and calibration
│   │   ├── config.py               GET /config/public — safe operational configuration
│   │   └── demo.py                 POST /simulate, GET /presets, /live-mode/*
│   ├── agent/
│   │   ├── gate.py                 Confidence gate: routes to fast path or reasoning path
│   │   ├── reasoning.py            LLM call + prompt assembly (Groq / Anthropic)
│   │   ├── executor.py             Bounded action executor: allow-list, spend cap, gating
│   │   ├── economics/
│   │   │   ├── scoring.py          Expected net recovery scoring formula
│   │   │   ├── probability_heuristics.py Calibrated Beta-shrinkage heuristics
│   │   │   └── historical_evidence.py Historical lookups with holdout isolation
│   │   ├── providers/
│   │   │   ├── groq_provider.py    Groq OpenAI-compatible provider
│   │   │   └── anthropic_provider.py Anthropic Claude provider
│   │   ├── prompts/
│   │   │   └── triage_system_prompt.md System prompt for triage reasoning
│   │   └── rules/
│   │       └── decline_taxonomy.py Fast-path decision table, documented per entry
│   ├── models/
│   │   ├── transaction.py          ORM model for incoming failed transaction
│   │   ├── audit_entry.py          ORM model for the audit trail
│   │   ├── recovery_decision.py    ORM model for evaluated options and winning choice
│   │   └── recovery_outcome.py     ORM model for post-execution measured results
│   ├── schemas/
│   │   ├── webhook.py              Pydantic schema for Razorpay webhook payloads
│   │   ├── triage.py               Pydantic schema for a triage decision
│   │   ├── recovery.py             Pydantic schemas for RecoveryOption, Context, Decision, Outcome
│   │   └── config.py               Pydantic schema for PublicConfigResponse
│   ├── services/
│   │   ├── razorpay_client.py      Thin wrapper around Razorpay SDK (test-mode only)
│   │   └── customer_history.py     Customer history retrieval contract
│   ├── db/
│   │   ├── session.py              SQLAlchemy engine and session factory
│   │   └── init_db.py              Database table initialization
│   └── utils/
│       └── money.py                INR formatting and financial calculations
├── scripts/
│   ├── generate_synthetic_data.py  Generates synthetic dataset and holdout partition
│   ├── seed_demo_database.py       Seeds local database with realistic demo cases
│   ├── run_evaluation.py           Runs multi-policy counterfactual evaluation
│   ├── run_llm_ablation.py         Runs LLM vs pure-economics ablation study
│   ├── analyze_training_calibration.py Direct calibration analysis on training set
│   └── diagnose_action_evaluation.py Error decomposition on holdout failures
├── data/
│   ├── synthetic/                  Generated working-set data
│   └── eval/                       Holdout data and frozen latest_report.json
├── tests/
│   ├── unit/                       Fast-path table, gate, scoring, calibration, public config
│   ├── integration/                Webhook loop, demo lifecycle, live mode, simulator
│   └── fixtures/                   Shared test fixtures (context_divergence_cases.json)
└── requirements.txt                Python dependency specifications
```
