# RECOVR frontend

React + TypeScript operations console for RECOVR. It presents read-only
backend evidence, an interactive failure simulator, and safe operational settings.

## Design Language & Tokens

The frontend is styled using Razorpay's real published design tokens extracted directly from the Blade design system source:
- **Brand Palette**: Intense brand blue (`hsla(218, 89%, 51%, 1)`), brand light (`hsla(218, 100%, 63%, 1)`), and subtle background tint (`hsla(218, 89%, 51%, 0.09)`).
- **Dark Palette**: The in-memory toggle uses Blade's published dark CSS tokens (not an inverted light palette): canvas `hsla(210, 5%, 8%, 1)` (`--surface-background-gray-moderate`), raised surface `hsla(210, 6%, 13%, 1)` (`--surface-background-gray-intense`), subtle surface `hsla(210, 4%, 11%, 1)`, border `hsla(216, 4%, 24%, 1)`, normal text `hsla(0, 0%, 100%, 1)`, and interactive primary `hsla(218, 100%, 63%, 1)`. Source: [packages/blade-core/src/tokens/theme.css Dark Mode block](https://github.com/razorpay/blade/blob/master/packages/blade-core/src/tokens/theme.css#L590-L733).
- **Blade Scales**: Exact typography font scale (`text-25` through `text-1100`), spacing scale (`0` through `11`), and border radius tokens (`xsmall` through `round`).
- **Persistent Header Badge**: Calm, clear "TEST MODE" badge in the top bar (`App.tsx`) communicating that no real money is at risk.
- **Brand Integrity**: Deliberately avoids inserting third-party trademarked logos, wordmarks, or proprietary assets.

## Run locally

```bash
cd frontend
npm install
npm run dev
```

The default API is `http://localhost:8000`. Set `VITE_API_BASE_URL` in
`.env.local` when needed.

## Current screens & components

- **Overview (`/`)**: High-level recovery metrics, KPI cards, and recent activity ledger.
- **Recoveries (`/recoveries`)**: Filterable ledger of active cases with path and execution mode filters.
- **Transactions (`/transactions`)**: Full transaction history with decline reasons and amounts.
- **Decision Detail (`/decisions/:id`)**: Full economic ranking breakdown (expected net value, risk penalties, costs), verbatim reasoning trace, and measured outcome.
- **Audit Trail (`/audit`)**: Verifiable chronological log of all decisions, gate evaluations, and provider attempts.
- **Evaluation (`/results`)**: Counterfactual comparison of policies (Retry-All, Fixed-Rule, RECOVR), regret analysis, five-seed robustness, and a reliability calibration chart (predicted vs. observed recovery rates).
- **Settings (`/settings`)**: Read-only operational configuration from `GET /config/public` (active LLM provider, models, batch spend cap, min auto confidence, credential status, and cost baseline).
- **Simulator Drawer (Header)**: Slide-over interactive failure simulator allowing operators to trigger realistic failure presets and observe live triage.

Execution mode and outcome are strictly decoupled: a real Razorpay attempt is not a recovery, simulated harness activity is never called a provider action, and null actual-recovery values are rendered as `Unavailable` rather than zero.

## Verification & Checks

```bash
npm run typecheck
npm run lint
npm run build
```
