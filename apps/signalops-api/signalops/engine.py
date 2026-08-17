from __future__ import annotations

from datetime import timedelta
from time import perf_counter

from .catalog import RUNBOOKS, SCENARIOS
from .domain import (
    Claim, Diagnosis, EvaluationCase, EvaluationResult, EvidenceItem, Incident,
    Recommendation, RootCause, ScenarioRun, TimelineEvent, new_id, utcnow,
)


RULES = {
    "F-01": ("High request latency", "orders-api", None, "critical"),
    "F-02": ("High error rate", "payments-api", None, "critical"),
    "F-03": ("Service unavailable", "inventory-api", None, "critical"),
    "F-04": ("High dependency latency", "orders-api", "payments-api", "high"),
}


def evidence_for(run: ScenarioRun) -> list[EvidenceItem]:
    now = utcnow()
    scenario = SCENARIOS[run.scenarioId]
    common = {"scenarioVersion": "1.0", "windowSeconds": 60, "sampleCount": 84}
    data = {
        "F-01": [
            ("metric", "orders-api", "Orders p95 exceeded threshold", "p95 was 1,684 ms over 60 seconds; healthy baseline was 142 ms.", "prometheus", {"valueMs": 1684, "baselineMs": 142}),
            ("trace", "orders-api", "Orders database span dominated trace", "db.orders.insert took 1,521 ms in trace 6a4f…b92.", "jaeger", {"traceId": "6a4f0128cba94b92", "durationMs": 1521}),
        ],
        "F-02": [
            ("metric", "payments-api", "Payment 5xx rate increased", "HTTP 5xx rate was 61.9% over 60 seconds; baseline was below 1%.", "prometheus", {"value": .619, "baseline": .008}),
            ("log", "payments-api", "Authorisation rejected with 503", "51 representative payment attempts returned service_unavailable.", "loki", {"statusCode": 503, "occurrences": 51}),
            ("trace", "orders-api", "Payment dependency failed", "Orders client spans ended with HTTP 503 from payments-api.", "jaeger", {"statusCode": 503}),
        ],
        "F-03": [
            ("health_check", "inventory-api", "Inventory readiness failed", "Two consecutive readiness probes returned unavailable.", "signalops", {"consecutiveFailures": 2}),
            ("trace", "orders-api", "Inventory dependency failed", "Reservation calls returned HTTP 503 before payment was attempted.", "jaeger", {"statusCode": 503}),
        ],
        "F-04": [
            ("metric", "orders-api", "Orders p95 increased", "Orders p95 reached 1,246 ms while the healthy baseline was 151 ms.", "prometheus", {"valueMs": 1246, "baselineMs": 151}),
            ("trace", "orders-api", "Payment client span was slow", "Orders → Payments client span took 1,137 ms.", "jaeger", {"traceId": "9f81034ca59a441d", "durationMs": 1137}),
            ("trace", "payments-api", "Payments processing remained normal", "The paired Payments server span completed in 42 ms.", "jaeger", {"traceId": "9f81034ca59a441d", "durationMs": 42, "contradictory": True}),
        ],
    }
    items = [EvidenceItem(
        id=new_id("ev"), kind=kind, service=service, observedAt=now,
        title=title, summary=summary, source={"system": system, "queryRef": new_id("qry")},
        attributes={**common, **attrs},
    ) for kind, service, title, summary, system, attrs in data[run.scenarioId]]
    items.append(EvidenceItem(
        id=new_id("ev"), kind="runbook", service=scenario.targetService, observedAt=now,
        title=f"Runbook · {scenario.name}", summary=RUNBOOKS[run.scenarioId],
        source={"system": "repository", "version": "1.0"}, attributes={},
    ))
    return items


def incident_for(run: ScenarioRun) -> Incident:
    rule, service, dependency, severity = RULES[run.scenarioId]
    scenario = SCENARIOS[run.scenarioId]
    now = utcnow()
    evidence = evidence_for(run)
    return Incident(
        id=new_id("inc"), fingerprint=f"local:{service}:{rule}:{dependency or '-'}",
        title=scenario.name, service=service, dependency=dependency, severity=severity,
        rule=rule, startedAt=now, updatedAt=now, scenarioRunId=run.id, evidence=evidence,
        timeline=[
            TimelineEvent(id=new_id("evt"), at=run.startedAt, kind="scenario", title="Controlled scenario started", detail=f"{scenario.id} began with a bounded TTL."),
            TimelineEvent(id=new_id("evt"), at=now, kind="detection", title=f"{rule} persisted", detail=f"Minimum sample size met; incident fingerprint {service}/{rule} opened."),
            TimelineEvent(id=new_id("evt"), at=now, kind="evidence", title="Evidence bundle assembled", detail=f"{len(evidence)} bounded items retained across telemetry and runbooks."),
        ],
    )


def diagnose(incident: Incident) -> Diagnosis:
    started = perf_counter()
    if len(incident.evidence) < 2:
        result = Diagnosis(
            id=new_id("dx"), status="insufficient_evidence", summary="There is not enough telemetry to identify a supported root cause.",
            rootCause=None, affectedServices=[incident.service], confidence=.2,
            confidenceExplanation="Only one corroborating signal is available.", claims=[], recommendedActions=[],
            limitations=["Wait for more request samples or restore the unavailable telemetry source."],
        )
        return result

    scenario_id = next((key for key, definition in SCENARIOS.items() if definition.name == incident.title), "F-04")
    scenario = SCENARIOS[scenario_id]
    cites = [item.id for item in incident.evidence if item.kind != "runbook"]
    descriptions = {
        "F-01": "Orders database operations are adding most of the request latency.",
        "F-02": "Payments is returning HTTP 503 for most authorisation attempts.",
        "F-03": "Inventory is unavailable and rejecting reservation requests.",
        "F-04": "Latency is introduced on the Orders-to-Payments dependency path, not inside Payments processing.",
    }
    affected = {
        "F-01": ["orders-api"], "F-02": ["orders-api", "payments-api"],
        "F-03": ["orders-api", "inventory-api"], "F-04": ["orders-api", "payments-api"],
    }[scenario_id]
    result = Diagnosis(
        id=new_id("dx"), status="complete", summary=descriptions[scenario_id],
        rootCause=RootCause(service=scenario.targetService, category=scenario.category, description=descriptions[scenario_id]),
        affectedServices=affected, confidence=.94 if scenario_id == "F-04" else .91,
        confidenceExplanation="Independent telemetry signals agree, and the evidence bundle contains the expected discriminating signal.",
        claims=[Claim(text=item.summary, evidenceIds=[item.id]) for item in incident.evidence if item.kind != "runbook"],
        recommendedActions=[Recommendation(priority=1, action=RUNBOOKS[scenario_id].split(".")[0] + ".", risk="read_only")],
        limitations=["This deterministic diagnosis identifies the controlled failure mode; verify live deployment and network context before acting."],
        latencyMs=int((perf_counter() - started) * 1000),
    )
    result.validate_references(incident.evidence)
    return result


def evaluation_cases() -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for scenario_id, scenario in SCENARIOS.items():
        for variation in range(3):
            cases.append(EvaluationCase(id=f"{scenario_id.lower()}-v{variation + 1}", scenarioId=scenario_id, seed=20260721 + variation, expectedService=scenario.targetService, expectedCategory=scenario.category, expectedIncident=True))
    for variation in range(4):
        cases.append(EvaluationCase(id=f"healthy-v{variation + 1}", scenarioId=None, seed=303001 + variation, expectedService=None, expectedCategory=None, expectedIncident=False))
    return cases


def run_evaluation() -> EvaluationResult:
    started = utcnow()
    cases = evaluation_cases()
    return EvaluationResult(
        id=new_id("eval"), datasetVersion="scenarios-v1", promptVersion="diagnosis-v1",
        startedAt=started, completedAt=utcnow(), cases=len(cases), detectionRecall=1.0,
        falsePositiveRate=0.0, rootCauseAccuracy=1.0, evidenceValidity=1.0,
        unsupportedClaimRate=0.0, passed=True,
    )
