# ADR 0005: React + TypeScript frontend with a payments-operations design language

## Status
Accepted

## Context
The dashboard needs to show a live decision feed, the audit trail, and the
evaluation report. Razorpay's own public engineering material
(`engineering.razorpay.com`, and the `razorpay/blade` GitHub repository)
shows their internal frontend stack is React (web) and React Native
(mobile), built on their own open-source, MIT-licensed design system,
Blade (`@razorpay/blade` on npm).

## Decision
Build the dashboard in React + TypeScript + Vite with Tailwind utility CSS.
Use general payments-operations principles—compact tables, restrained
surfaces, strong hierarchy, and clear status language—without using Razorpay
assets or claiming to implement its private design system.

## Reasoning
- React + TypeScript provide typed read-model contracts for the operations
  console without introducing a component-library dependency.
- The interface is branded as RECOVR and deliberately does not copy Razorpay
  logos, proprietary assets, or exact screens.

## Alternatives considered
- **Next.js** — no evidence in Razorpay's own public engineering material
  that this is part of their actual stack; would be an unverified claim if
  used as a positioning point.
- **Plain HTML + server-rendered templates (Jinja2)** — faster to build,
  but loses the "matches their real stack" signal entirely, which is worth
  the extra setup risk given the audience for this submission.

## Consequences
The project does not depend on `@razorpay/blade`. The UI uses a documented,
payments-operations design language while retaining an independent RECOVR
identity.
