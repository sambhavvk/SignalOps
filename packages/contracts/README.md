# API contracts

All public APIs are versioned under `/api/v1`. The SignalOps control plane publishes its generated OpenAPI contract at `/openapi.json` and interactive reference at `/docs`.

Shared conventions:

- Propagate `traceparent` and `X-Correlation-ID` on downstream requests.
- Require `Idempotency-Key` for order, payment, and reservation creation.
- Return machine-readable `code` plus a safe `message` for documented failures.
- Bound list queries and evidence windows; clients must not submit raw PromQL, LogQL, SQL, or trace-store queries.
