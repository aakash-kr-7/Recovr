# ADR 0005: React + TypeScript frontend with a payments-operations design language

## Status
Accepted

## Context
The dashboard needs to show a live decision feed, the audit trail, and the evaluation report. Razorpay's own public engineering material (`engineering.razorpay.com`, and the `razorpay/blade` GitHub repository) shows their internal frontend stack is React (web) and React Native (mobile), built on their own open-source, MIT-licensed design system, Blade (`@razorpay/blade` on npm).

We attempted to adopt `@razorpay/blade` for this project to authentically match their component stack.

## Decision
Build the dashboard in React + TypeScript + Vite with Tailwind utility CSS, using Blade's **published design tokens** (colors, typography, spacing) mapped into Tailwind classes, rather than using Blade's React components.

An earnest attempt to install `@razorpay/blade` was blocked by an upstream React version conflict. Blade transitively depends on React Native (even for web-only setups) via `@floating-ui/react-native`. That dependency chain resolves to a `react-native` version requiring React 19, which strictly conflicts with this project's React 18 web setup. The exact blocking error encountered was:

```
npm error Could not resolve dependency:
npm error peer react@"^19.2.3" from react-native@0.87.1
npm error node_modules/react-native
npm error   peer react-native@">=0.64.0" from @floating-ui/react-native@0.10.10
npm error   node_modules/@floating-ui/react-native
npm error     peer @floating-ui/react-native@"^0.10.0" from @razorpay/blade@12.121.1
```

Rather than forcing the installation with `--legacy-peer-deps` (which risks silent bundling issues right before a demo), we decided to fall back to standard Tailwind CSS. 

## Consequences
The project does not depend on the `@razorpay/blade` component package. Instead, the UI is styled using Razorpay's real published design tokens extracted directly from Blade's source, ensuring the visual language is authentically Razorpay's while retaining an independent RECOVR identity and stable React 18 build.
