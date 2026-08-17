# Architecture overview

SignalOps separates operational state from telemetry and keeps diagnosis read-only.

```mermaid
flowchart LR
  Browser --> Web
  Web --> Control[SignalOps API]
  Traffic[Traffic generator] --> Orders
  Orders --> Inventory
  Orders --> Payments
  Orders & Inventory & Payments --> OTEL[OTel collector]
  OTEL --> Prometheus & Loki & Jaeger
  Worker --> Control
  Control --> Evidence[Bounded evidence bundle]
  Evidence --> Mock[Deterministic diagnosis]
```

The four scenario types are the only accepted fault controls. Each fault has a bounded TTL and is cleared by the target service without relying on a browser connection. Diagnosis claims must cite supplied evidence IDs, and recommendations must be classified `read_only`.
