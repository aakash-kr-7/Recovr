# RECOVR

**A payment-failure triage agent for Razorpay's AI Buildathon, Track 3 (Revenue Recovery).**

Not every failed payment is lost money. Some failures are permanent (card reported lost, account closed). Many are temporary and fixable (a bank timeout, an expired session, a card that was momentarily maxed out). Traditional retry tools treat every failure uniformly: match the decline code to a fixed rule, run the rule.

RECOVR reads the decline reason **and the transaction's context**, ranks permitted actions by expected net recovery, and records each execution and outcome. Its only provider action is a Razorpay test-mode Payment Link; it is never called recovered until a later provider outcome confirms it. The evaluation report is a clearly labeled synthetic, held-out action-economics comparison — not merchant revenue.

Current limitation: live customer-history retrieval is a documented stub that returns an empty history. The structured context contract and its synthetic test coverage exist, but the product must not claim live Razorpay historical enrichment until that lookup is implemented.

> **Read this first:** [`docs/POSITIONING.md`](docs/POSITIONING.md) is the single most important document in this repo. It states plainly what is and isn't novel here, names the existing products this overlaps with (Razorpay's own smart routing, Slicker, GR4VY, Stripe Smart Retries), and explains the actual differentiation: an optional bounded reasoning path for ambiguous cases, economic action ranking, and an auditable synthetic evaluation.

---

## What's in this repo

| Path | What it is |
|---|---|
| [`backend/`](backend/) | FastAPI service: webhook intake, two-path triage agent (Groq / Claude), economic scoring layer, bounded action executor, audit trail, demo simulator, live-mode playback streamer, safe public config, and evaluation harness |
| [`frontend/`](frontend/) | React + TypeScript operations console: dashboard with recovery funnel, dedicated live mode streamer, recoveries workspace, decision detail viewer, audit trail with deep inspector, counterfactual evaluation, guided tour, and settings console |
| [`docs/`](docs/) | Positioning, architecture overview, evaluation methodology, failure log, demo validation, evidence freeze, and architecture decision records (ADRs 0001–0007) |
| [`.github/workflows/`](.github/workflows/) | CI: lint + test on every push |

---

## Key Features

1. **Two-Path Triage Agent**: Fast-path deterministic routing for unambiguous decline reasons; an optional reasoning path (Groq OpenAI-compatible or Anthropic Claude) over structured customer context, timing, and raw decline text.
2. **Economic Decision Engine**: Ranks every permitted action (`retry_same_rail`, `retry_alt_rail`, `escalate_to_dunning`, `hold_for_review`, `no_action`) by expected net recovery value; economics overrides candidate actions when costs/penalties exceed probability gains.
3. **Bounded Action Executor**: Enforces strict allow-listing, per-customer retry limits, and a ₹50,000 batch spend cap. Low-confidence reasoning outputs fail-close to human review (`hold_for_review`).
4. **Dedicated Live Mode (`/live`)**: Real-time streaming playback of 10 canonical failure scenarios (transient timeouts, repeat offenders, compliance blocks, spend cap limits, unmapped bank errors) with step progress, pause/resume, and session-isolated metrics.
5. **Interactive Payment Failure Simulator**: Built-in slide-over drawer allowing operators to trigger and inspect custom or preset failure scenarios in real time.
6. **Recoveries & Audit Trail Workspace**: Filterable recovery ledger (`/recoveries`) and comprehensive chronological audit trail (`/audit`) with a deep transaction inspector modal.
7. **Safe Operational Settings (`GET /config/public`)**: Read-only settings page exposing active operational bounds (LLM provider, models, spend cap, confidence thresholds, credential status, and cost baseline) while strictly excluding all secrets, API keys, and connection strings.
8. **Authentic Design Tokens (Razorpay Blade)**: The UI is styled with authentic Razorpay design tokens (colors, type scale, spacing, border radiuses) mapped into Tailwind classes, including dark and light theme modes, merchant operator switching, interactive guided tour, and a persistent "TEST MODE" badge.

---

## Quick start

See [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md) for full setup.

### 1. Backend Setup

```bash
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
```

### 2. Frontend Setup (in a separate terminal)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` for the dashboard, or `http://localhost:8000/docs` for the OpenAPI documentation.

---

## Architecture & Data Flow

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
Formula: probability × amount × recovery_fraction − action_cost − risk_penalty
        │
        ▼
Bounded action executor (allow-list, ₹50k spend cap, confidence gating)
        │
        ▼
Execute permitted action (Payment Link) → log decision + reasoning + outcome
        │
   ┌────┴────────────────────────┬─────────────────────────┐
   ▼                             ▼                         ▼
Audit Log & Recovery Decision   Provider Outcome     Operational Console
(app/models/audit_entry.py)   (real / simulated)   (Dashboard / Live Mode)
```

Full detail in [`docs/architecture/overview.md`](docs/architecture/overview.md).

---

## Primary API Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/webhooks/razorpay` | Intake for incoming `payment.failed` webhooks (verifies HMAC signatures). |
| `GET` | `/transactions/recent` | Live read model for recent triage decisions and execution statuses. |
| `GET` | `/transactions/funnel-summary` | Aggregated failure/recovery funnel metrics (`session` or `all` scope). |
| `GET` | `/transactions/audit/{id}` | Detailed lifecycle trace, evaluated options, and reasoning text for a transaction. |
| `GET` | `/evaluation/latest` | Synthetic action-economics evaluation report, counterfactual metrics, and calibration curve. |
| `GET` | `/config/public` | Safe operational parameters (active LLM provider, spend cap, thresholds, cost constants). Secrets are strictly excluded. |
| `GET` | `/demo/presets` | Preset failure scenarios for interactive demonstration. |
| `POST` | `/demo/simulate` | Trigger real-time end-to-end payment failure triage with immediate execution outcome. |
| `POST` | `/demo/live-mode/start` | Start the automated streaming playback loop of canonical failure scenarios. |
| `POST` | `/demo/live-mode/stop` | Stop / pause the active live-mode streaming loop. |
| `GET` | `/demo/live-mode/status` | Current playback state, sequence progress, and active scenario. |
| `GET` | `/health` | Health check endpoint. |

---

## Evaluation & Calibration

Every evaluation claim is backed by a held-out **synthetic** test set the system's own tuning never saw. The frozen configuration uses Beta-shrinkage calibration and structured context; its measured calibration result is specific to that synthetic evaluation, not a production recovery claim. See [`docs/architecture/failure_log.md`](docs/architecture/failure_log.md#entry-3-empirical-calibration-of-action-probabilities-and-recovery-fractions) for the full account of how systematic underestimation was diagnosed and corrected during our honest-iteration process.

Run the evaluation yourself:

```bash
cd backend
python scripts/run_evaluation.py
```

This evaluates selected actions against synthetic hidden counterfactual outcomes, reports simulated net recovery, regret, and opportunity loss, and writes the full report to `backend/data/eval/latest_report.json`. The frontend Evaluation view renders the calibration curve (predicted probability vs. observed recovery rate) directly from this report. Legacy binary precision/recall remain secondary diagnostics. See [`docs/architecture/evaluation.md`](docs/architecture/evaluation.md).

---

## What broke, and how we got out

Documented honestly, with the real failing cases, in [`docs/architecture/failure_log.md`](docs/architecture/failure_log.md) — this is a required field on the buildathon application, and we treat it the same way here: as a real account, not a staged one.

---

## Project status & Decisions

Built for the Razorpay AI Buildathon. The frontend is styled using Razorpay's real published design tokens (extracted from Blade). See [`docs/decisions/`](docs/decisions/) for the architecture decision records explaining the calls made along the way:
- [ADR 0001: Why FastAPI](docs/decisions/0001-why-fastapi.md)
- [ADR 0002: No Custom Model (LLM with structured context)](docs/decisions/0002-no-custom-model.md)
- [ADR 0003: Two-Path Agent (Deterministic + Reasoning)](docs/decisions/0003-two-path-agent.md)
- [ADR 0004: Baseline Sourcing](docs/decisions/0004-baseline-sourcing.md)
- [ADR 0005: Frontend Stack (React + Vite + Blade Design Tokens)](docs/decisions/0005-frontend-stack.md)
- [ADR 0006: Economic Decision Layer (Separate Decision & Outcome Schemas)](docs/decisions/0006-economic-decision-layer.md)
- [ADR 0007: Live Mode Streaming Simulation](docs/decisions/0007-live-mode-simulation.md)

---

## License

MIT — see [`LICENSE`](LICENSE).
