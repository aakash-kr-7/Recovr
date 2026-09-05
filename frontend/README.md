# RECOVR — Frontend

React + TypeScript operations console for RECOVR. It presents read-only backend evidence, real-time streaming live-mode playback, an interactive failure simulator, a comprehensive audit trail with transaction inspection, and safe operational settings.

---

## Design Language & Authentic Tokens (Razorpay Blade)

The frontend is styled using Razorpay's real published design tokens extracted directly from the Blade design system source:
- **Brand Palette**: Intense brand blue (`hsla(218, 89%, 51%, 1)`), brand light (`hsla(218, 100%, 63%, 1)`), and subtle background tint (`hsla(218, 89%, 51%, 0.09)`).
- **Theme Support (Dark & Light Mode)**: Uses Blade's published CSS tokens:
  - Dark mode canvas: `hsla(210, 5%, 8%, 1)` (`--surface-background-gray-moderate`), raised surface `hsla(210, 6%, 13%, 1)` (`--surface-background-gray-intense`), subtle surface `hsla(210, 4%, 11%, 1)`, border `hsla(216, 4%, 24%, 1)`, text `hsla(0, 0%, 100%, 1)`, and interactive primary `hsla(218, 100%, 63%, 1)`.
  - Light mode canvas: clean, high-contrast slate surfaces with Blade border and typography tokens.
  - Interactive theme toggle located in the persistent top bar.
- **Blade Scales**: Exact typography scale (`text-25` through `text-1100`), spacing scale (`0` through `11`), and border radius tokens (`xsmall` through `round`).
- **Persistent Header Badge**: Calm, clear "TEST MODE" badge communicating that no real money is at risk.
- **Merchant Workspace & Operator Identity**: Merchant workspace context with operator profile avatar, workspace switching, and session persistence (`MerchantContext`, `LoginPage`).
- **Brand Integrity**: Deliberately avoids inserting third-party trademarked logos, wordmarks, or proprietary assets.

---

## Run Locally

```bash
cd frontend
npm install
npm run dev
```

The default backend API URL is `http://localhost:8000`. Set `VITE_API_BASE_URL` in `.env.local` when using a custom port or proxy.

---

## Current Screens & Components

- **Dashboard (`/`)**: High-level recovery metrics, KPI cards (Recovered volume, Attempted volume, Honest Recovery Rate excluding pending review cases, Net Profit), Recovery Funnel, Recovery Chart, and Recent Activity ledger.
- **Live Mode (`/live`)**: Dedicated streaming command console with 10-step interactive scenario stepper, real-time playback controls (Start/Stop/Pause), and live decision stream.
- **Recoveries (`/recoveries`)**: Comprehensive operational ledger of all failure recovery attempts with filters for execution mode, triage path, decline reason, and status. (`/transactions` redirects here for a unified recoveries experience).
- **Decision Detail (`/decisions/:id`)**: Full economic ranking breakdown (expected net value, risk penalties, action costs), verbatim reasoning trace, and verified execution outcome.
- **Audit Trail (`/audit`)**: Verifiable chronological log of all decisions, gate evaluations, and provider attempts, featuring a Deep Transaction Inspector modal.
- **Evaluation (`/results`)**: Counterfactual comparison of policies (Retry-All, Fixed-Rule, RECOVR), regret analysis, five-seed robustness, and a reliability calibration chart (predicted vs. observed recovery rates).
- **Settings (`/settings`)**: Read-only operational configuration from `GET /config/public` (active LLM provider, models, batch spend cap, min auto confidence, credential status, and cost baseline).
- **Simulator Drawer (Header)**: Slide-over interactive failure simulator allowing operators to trigger realistic failure presets and observe live triage.
- **Guided Product Tour**: In-app step-by-step onboarding walkthrough ("Take a tour" button) guiding judges and operators through the core interface.
- **Merchant Login (`/login`)**: Operator workspace login and merchant profile selector.

---

## Verification & Checks

```bash
npm run build     # Type-checks (tsc -b) and bundles production assets via Vite
npm run lint      # Runs ESLint code-quality verification
```
