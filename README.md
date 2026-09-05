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
| [`backend/`](backend/) | FastAPI service: webhook intake, the two-path triage agent, the economic scoring layer, the bounded action executor, the audit trail, and the evaluation harness |
| [`frontend/`](frontend/) | React + TypeScript dashboard: live decision feed, audit trail viewer, recovery report |
| [`docs/`](docs/) | Positioning, architecture, and the decision log (see below) |
| [`.github/workflows/`](.github/workflows/) | CI: lint + test on every push |

## Quick start

See [`backend/README.md`](backend/README.md) and
[`frontend/README.md`](frontend/README.md) for full setup. The short version:

```bash
# Backend
cd backend
cp .env.example .env        # fill in your Razorpay TEST-mode keys
pip install -r requirements.txt
python scripts/generate_synthetic_data.py   # builds the labeled dataset
uvicorn app.main:app --reload

# Frontend, in a second terminal
cd frontend
npm install
npm run dev
```

Then open `http://localhost:5173` for the dashboard, or `http://localhost:8000/docs`
for the raw API.

## How it works, in one diagram

```
Payment fails (Razorpay webhook)
        │
        ▼
Confidence gate: is this decline reason unambiguous?
        │
   ┌────┴────┐
   ▼         ▼
Deterministic   Optional LLM reasoning path
fast path       (customer history + timing + decline text)
   │         │
   └────┬────┘
        ▼
Bounded action executor (spend caps, allow-listed actions only)
        │
        ▼
Execute permitted action → log decision + reasoning + outcome
```

Full detail in [`docs/architecture/overview.md`](docs/architecture/overview.md).

## Evaluation

Every evaluation claim is backed by a held-out **synthetic** test set the
system's own tuning never saw. The frozen configuration uses Beta-shrinkage
calibration and structured context; its measured calibration result is
specific to that synthetic evaluation, not a production recovery claim. See [`docs/architecture/failure_log.md`](docs/architecture/failure_log.md#entry-3-empirical-calibration-of-action-probabilities-and-recovery-fractions)
for the full account of how systematic underestimation was diagnosed and
corrected during our honest-iteration process.

Run it yourself:

```bash
cd backend
python scripts/run_evaluation.py
```

This evaluates selected actions against synthetic hidden counterfactual
outcomes, reports simulated net recovery, regret, and opportunity loss, and
writes the full report to `backend/data/eval/latest_report.json`. Legacy
binary precision/recall remain secondary diagnostics. See
[`docs/architecture/evaluation.md`](docs/architecture/evaluation.md) for
what each metric means and why it's the bar we chose to hold ourselves to.

## What broke, and how we got out

Documented honestly, with the real failing case, in
[`docs/architecture/failure_log.md`](docs/architecture/failure_log.md) —
this is a required field on the buildathon application, and we treat it the
same way here: as a real account, not a staged one.

## Project status

Built solo, in one week, for the Razorpay AI Buildathon. See
[`docs/decisions/`](docs/decisions/) for the architecture decision records
explaining the calls made along the way (why FastAPI, why the two-path
agent, and why SQLite).

## License

MIT — see [`LICENSE`](LICENSE).
