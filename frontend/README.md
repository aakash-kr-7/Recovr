# RECOVR frontend

React + TypeScript operations console for RECOVR. It presents read-only
backend evidence; it does not execute recovery actions.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

The default API is `http://localhost:8000`. Set `VITE_API_BASE_URL` in
`.env.local` when needed.

## Current screens

- Overview, recoveries, and transaction ledger read `GET /transactions/recent`.
- Decision detail reads `GET /transactions/audit/{transaction_id}`.
- Audit Trail uses the same transaction read model.
- Evaluation reads `GET /evaluation/latest` and labels every displayed value
  as synthetic evaluation data.

Execution mode and outcome are separate: a real Razorpay attempt is not a
recovery, simulated harness activity is not a provider action, and a null
actual-recovery value is rendered as unavailable rather than zero.

## Checks

```bash
npm run typecheck
npm run build
npm run lint
```
