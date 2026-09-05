# ADR 0001: FastAPI for the backend

## Status
Accepted

## Context
Needed a backend that can receive Razorpay webhooks, run the triage
pipeline, expose a small REST API for the dashboard, and be built cleanly
solo within a one-week window.

## Decision
FastAPI, Python 3.11+.

## Reasoning
- Async-native, which matters for webhook intake under load and for
  calling out to the Claude API without blocking.
- Pydantic models give free request/response validation, which doubles as
  living documentation for the decline-event and audit-entry schemas —
  useful for anyone (a judge, a future teammate) reading the code cold.
- Auto-generated OpenAPI docs at `/docs` mean the API is self-documenting
  with zero extra effort, which matters when the write-up budget for a
  one-week build is scarce.
- Prior working familiarity with FastAPI removes a whole axis of risk from
  an already tight timeline — this is not the week to learn a new
  framework.

## Alternatives considered
- **Django REST Framework** — heavier, more batteries-included than this
  project needs; slower to stand up a lean webhook + agent service.
- **Node/Express** — would match a hypothetical all-JS stack, but the
  reasoning/rules logic benefits from Python's data-handling ergonomics,
  and splitting stacks (Python agent core + Node API shim) adds
  integration risk for no real benefit here.

## Consequences
Frontend is a separate React/TypeScript app talking to this over HTTP,
rather than a single full-stack framework. Accepted deliberately — see
ADR 0005.
