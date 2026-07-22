# SignalOps

SignalOps is a deterministic, evidence-first incident investigation demo. It combines a small commerce system (Orders, Payments, and Inventory), controlled fault injection, an incident control plane, and a portfolio-ready investigation workspace.

## Quick start

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Open `http://localhost:3000` for the product and `http://localhost:8000/docs` for the control API.

The default diagnosis provider is deterministic and requires no API key. The dashboard also runs with realistic demo data when the API is unavailable, so the product story remains inspectable while infrastructure starts.

## Firebase deployment

The public dashboard is exported as a static, client-hydrated build and deployed to the isolated Firebase Hosting site `signalops-sambhavvk` in project `portfolio-c1ae4`:

```powershell
./scripts/deploy-firebase.ps1
```

Set `NEXT_PUBLIC_SIGNALOPS_API_URL` before building when the control API is available on a public HTTPS endpoint. The local multi-container backend is not uploaded to static Hosting. For a hosted full-stack environment, deploy the API containers to Cloud Run and add Firebase Hosting rewrites for `/api/**`.

## Demonstration

```powershell
./scripts/bootstrap.ps1
./scripts/up.ps1
./scripts/scenario.ps1 F-04 180
```

Open the active incident, inspect the metric/trace/log evidence, run the diagnosis, then clear the fault from the Scenarios view. Faults are allow-listed, demo-only, and expire automatically after at most ten minutes.

## Components

- `apps/web`: SignalOps product interface
- `apps/signalops-api`: incident, evidence, diagnosis, scenario, and evaluation APIs
- `apps/signalops-worker`: deterministic detector loop
- `apps/traffic-generator`: reproducible order traffic
- `services/*`: ASP.NET Core commerce APIs
- `infrastructure/*`: OpenTelemetry, Prometheus, Loki, and Grafana configuration
- `scenarios/definitions`: versioned fault and evaluation fixtures

See [docs/demo-script.md](docs/demo-script.md) for the five-minute walkthrough and [docs/architecture/overview.md](docs/architecture/overview.md) for trust boundaries and design decisions.

## Safety model

SignalOps only exposes four bounded demo faults. Diagnosis is read-only: providers receive a size-limited evidence bundle, citations are validated, and only `read_only` recommendations are accepted. Telemetry and runbooks are treated as untrusted data, never executable instructions.
