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

API docs at `http://localhost:8000/docs`.

## Run the evaluation

```bash
python scripts/run_evaluation.py
```

Writes the synthetic action-economics evaluation report to
`data/eval/latest_report.json`; binary diagnostics are secondary.

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
    webhooks.py        POST /webhooks/razorpay — payment.failed intake
    transactions.py     GET endpoints the dashboard reads
    evaluation.py        GET endpoint serving the latest eval report
  agent/
    gate.py             Confidence gate: routes to fast path or reasoning path
    reasoning.py          Claude API call + prompt assembly for the reasoning path
    executor.py            Bounded action executor: allow-list + spend cap + gating
    prompts/
      triage_system_prompt.md
    rules/
      decline_taxonomy.py    Fast-path decision table, documented per entry
  models/
    transaction.py        ORM model for an incoming failed transaction
    audit_entry.py          ORM model for the audit trail
  schemas/
    webhook.py              Pydantic schema for Razorpay webhook payloads
    triage.py                 Pydantic schema for a triage decision
  services/
    razorpay_client.py         Thin wrapper around the Razorpay SDK, test-mode only
  db/
    session.py                  SQLite engine/session setup
    init_db.py                    Table creation
  utils/
    money.py                       ₹ formatting and cost-calculation helpers
scripts/
  generate_synthetic_data.py
  run_evaluation.py
data/
  synthetic/           Generated working-set data (gitignored)
  eval/                Generated holdout + eval reports (gitignored)
tests/
  unit/                Fast-path table, gate logic, executor bounds
  integration/          End-to-end webhook → decision → audit entry
  fixtures/              Shared test fixtures, incl. context_divergence_cases.json
```
