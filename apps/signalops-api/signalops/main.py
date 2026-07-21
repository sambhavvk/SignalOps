from __future__ import annotations

import asyncio
import os
from datetime import timedelta

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .catalog import SCENARIOS
from .domain import IncidentStatus, ScenarioRun, ScenarioStart, TimelineEvent, new_id, utcnow
from .engine import diagnose, incident_for, run_evaluation
from .store import StateStore


app = FastAPI(title="SignalOps Control API", version="1.0.0", docs_url="/docs")
allowed_origins = [origin.strip() for origin in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,https://signalops-sambhavvk.web.app",
).split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=["*"], allow_headers=["*"])
store = StateStore()


def require_demo_token(x_fault_control_token: str = Header(default="")) -> None:
    if os.getenv("DEMO_MODE", "true").lower() != "true":
        raise HTTPException(status_code=403, detail="Fault controls are disabled outside demo mode")
    if x_fault_control_token != os.getenv("FAULT_CONTROL_TOKEN", "signalops-local-demo"):
        raise HTTPException(status_code=401, detail="Invalid fault-control credential")


async def propagate_fault(scenario_id: str, ttl: int, clear: bool = False) -> None:
    routes = {
        "F-01": (os.getenv("ORDERS_URL", "http://localhost:8100"), "slow-database"),
        "F-02": (os.getenv("PAYMENTS_URL", "http://localhost:8101"), "error-surge"),
        "F-03": (os.getenv("INVENTORY_URL", "http://localhost:8102"), "unavailable"),
        "F-04": (os.getenv("ORDERS_URL", "http://localhost:8100"), "payment-latency"),
    }
    base, fault = routes[scenario_id]
    headers = {"X-Fault-Control-Token": os.getenv("FAULT_CONTROL_TOKEN", "signalops-local-demo")}
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            if clear:
                await client.delete(f"{base}/api/v1/demo/faults/{fault}", headers=headers)
            else:
                await client.post(f"{base}/api/v1/demo/faults", headers=headers, json={"type": fault, "ttlSeconds": ttl})
    except httpx.HTTPError:
        pass  # Control-plane state remains usable when a demo service is still starting.


def reconcile() -> None:
    now = utcnow()
    changed = False
    for run in store.runs.values():
        if run.status == "active" and run.expiresAt <= now:
            run.status, run.clearedAt = "expired", now
            for incident in store.incidents.values():
                if incident.scenarioRunId == run.id and incident.status in {IncidentStatus.OPEN, IncidentStatus.INVESTIGATING}:
                    incident.status, incident.resolvedAt, incident.updatedAt = IncidentStatus.RESOLVED, now, now
                    incident.timeline.append(TimelineEvent(id=new_id("evt"), at=now, kind="recovery", title="Service recovered", detail="The bounded fault expired and recovery conditions were satisfied."))
            changed = True
    if changed:
        store.save()


@app.get("/health/live")
def live():
    return {"status": "live"}


@app.get("/health/ready")
def ready():
    return {"status": "ready", "provider": os.getenv("DIAGNOSIS_PROVIDER", "mock")}


@app.get("/api/v1/overview")
def overview():
    reconcile()
    open_incidents = [x for x in store.incidents.values() if x.status in {IncidentStatus.OPEN, IncidentStatus.INVESTIGATING}]
    active = [x for x in store.runs.values() if x.status == "active"]
    degraded = {x.service for x in open_incidents}
    return {
        "overallStatus": "degraded" if degraded else "healthy",
        "freshAt": utcnow(),
        "services": [
            {"name": name, "displayName": display, "status": "degraded" if name in degraded else "healthy", "requestRate": rate, "p95Ms": p95, "errorRate": error}
            for name, display, rate, p95, error in [
                ("orders-api", "Orders", 42.8, 1246 if "orders-api" in degraded else 151, .032),
                ("payments-api", "Payments", 39.4, 42, .008),
                ("inventory-api", "Inventory", 43.1, 67, .003),
            ]
        ],
        "openIncidents": len(open_incidents), "activeScenarios": len(active),
    }


@app.get("/api/v1/incidents")
def incidents(status_filter: str | None = Query(default=None, alias="status"), service: str | None = None):
    reconcile()
    values = list(store.incidents.values())
    if status_filter:
        values = [x for x in values if x.status == status_filter]
    if service:
        values = [x for x in values if x.service == service]
    return {"items": sorted(values, key=lambda x: x.startedAt, reverse=True), "nextCursor": None}


@app.get("/api/v1/incidents/{incident_id}")
def incident_detail(incident_id: str):
    reconcile()
    if incident_id not in store.incidents:
        raise HTTPException(status_code=404, detail="Incident not found")
    return store.incidents[incident_id]


@app.post("/api/v1/incidents/{incident_id}/diagnoses", status_code=status.HTTP_202_ACCEPTED)
def create_diagnosis(incident_id: str):
    incident = store.incidents.get(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    incident.status = IncidentStatus.INVESTIGATING
    incident.diagnosis = diagnose(incident)
    incident.updatedAt = utcnow()
    incident.timeline.append(TimelineEvent(id=new_id("evt"), at=incident.updatedAt, kind="diagnosis", title="Evidence-backed diagnosis completed", detail=f"{len(incident.diagnosis.claims)} claims passed citation validation."))
    store.save()
    return incident.diagnosis


@app.get("/api/v1/scenarios")
def scenarios():
    reconcile()
    active_by_scenario = {run.scenarioId: run for run in store.runs.values() if run.status == "active"}
    return [{**scenario.model_dump(), "activeRun": active_by_scenario.get(scenario.id)} for scenario in SCENARIOS.values()]


@app.post("/api/v1/scenarios/runs", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_demo_token)])
async def start_scenario(request: ScenarioStart):
    reconcile()
    if any(x.status == "active" for x in store.runs.values()):
        raise HTTPException(status_code=409, detail="Clear the active scenario before starting another")
    now = utcnow()
    run = ScenarioRun(id=new_id("run"), scenarioId=request.scenarioId, startedAt=now, expiresAt=now + timedelta(seconds=request.ttlSeconds))
    incident = incident_for(run)
    store.runs[run.id], store.incidents[incident.id] = run, incident
    store.save()
    await propagate_fault(request.scenarioId, request.ttlSeconds)
    return {"run": run, "incidentId": incident.id}


@app.delete("/api/v1/scenarios/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_demo_token)])
async def clear_scenario(run_id: str):
    run = store.runs.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Scenario run not found")
    if run.status == "active":
        now = utcnow(); run.status = "cleared"; run.clearedAt = now
        for incident in store.incidents.values():
            if incident.scenarioRunId == run.id and incident.status != IncidentStatus.CLOSED:
                incident.status, incident.resolvedAt, incident.updatedAt = IncidentStatus.RESOLVED, now, now
                incident.timeline.append(TimelineEvent(id=new_id("evt"), at=now, kind="recovery", title="Recovery confirmed", detail="The controlled fault was cleared and service health returned to its normal range."))
        store.save(); await propagate_fault(run.scenarioId, 0, clear=True)
    return Response(status_code=204)


@app.post("/api/v1/detector/evaluate")
def detector_evaluate():
    reconcile()
    return {"evaluatedAt": utcnow(), "activeIncidents": sum(x.status in {IncidentStatus.OPEN, IncidentStatus.INVESTIGATING} for x in store.incidents.values())}


@app.get("/api/v1/evaluations")
def evaluations():
    return {"items": sorted(store.evaluations.values(), key=lambda x: x.startedAt, reverse=True)}


@app.post("/api/v1/evaluations", status_code=status.HTTP_201_CREATED)
def create_evaluation():
    result = run_evaluation(); store.evaluations[result.id] = result; store.save(); return result


@app.get("/api/v1/events")
async def events():
    async def stream():
        while True:
            reconcile()
            yield f"event: heartbeat\ndata: {{\"at\": \"{utcnow().isoformat()}\"}}\n\n"
            await asyncio.sleep(10)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
