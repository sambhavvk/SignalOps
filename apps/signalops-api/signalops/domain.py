from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:16]}"


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    CLOSED = "closed"


class EvidenceItem(BaseModel):
    id: str
    kind: Literal["metric", "log", "trace", "health_check", "topology", "runbook"]
    service: str
    observedAt: datetime
    title: str
    summary: str
    source: dict[str, Any]
    attributes: dict[str, Any] = Field(default_factory=dict)


class TimelineEvent(BaseModel):
    id: str
    at: datetime
    kind: str
    title: str
    detail: str


class Incident(BaseModel):
    id: str
    fingerprint: str
    title: str
    service: str
    dependency: str | None = None
    severity: Literal["critical", "high", "medium", "low"] = "high"
    status: IncidentStatus = IncidentStatus.OPEN
    rule: str
    startedAt: datetime
    updatedAt: datetime
    resolvedAt: datetime | None = None
    scenarioRunId: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    diagnosis: "Diagnosis | None" = None


class RootCause(BaseModel):
    service: str
    category: str
    description: str


class Claim(BaseModel):
    text: str
    evidenceIds: list[str] = Field(min_length=1)


class Recommendation(BaseModel):
    priority: int = Field(ge=1, le=5)
    action: str
    risk: Literal["read_only"]


class Diagnosis(BaseModel):
    id: str
    status: Literal["complete", "insufficient_evidence"]
    summary: str
    rootCause: RootCause | None
    affectedServices: list[str]
    confidence: float = Field(ge=0, le=1)
    confidenceExplanation: str
    claims: list[Claim]
    recommendedActions: list[Recommendation]
    limitations: list[str]
    provider: str = "mock"
    model: str = "deterministic-v1"
    promptVersion: str = "diagnosis-v1"
    latencyMs: int = 0
    createdAt: datetime = Field(default_factory=utcnow)

    def validate_references(self, evidence: list[EvidenceItem]) -> None:
        allowed = {item.id for item in evidence}
        invalid = {ref for claim in self.claims for ref in claim.evidenceIds if ref not in allowed}
        if invalid:
            raise ValueError(f"Unknown evidence references: {sorted(invalid)}")


class ScenarioDefinition(BaseModel):
    id: str
    name: str
    targetService: str
    category: str
    description: str
    injection: str
    expectedSignal: str
    defaultTtlSeconds: int = 180
    maximumTtlSeconds: int = 600


class ScenarioRun(BaseModel):
    id: str
    scenarioId: str
    status: Literal["active", "cleared", "expired"] = "active"
    startedAt: datetime = Field(default_factory=utcnow)
    expiresAt: datetime
    clearedAt: datetime | None = None


class ScenarioStart(BaseModel):
    scenarioId: str
    ttlSeconds: int = Field(default=180, ge=30, le=600)

    @field_validator("scenarioId")
    @classmethod
    def allow_listed(cls, value: str) -> str:
        if value not in {"F-01", "F-02", "F-03", "F-04"}:
            raise ValueError("scenarioId must be one of F-01 through F-04")
        return value


class EvaluationCase(BaseModel):
    id: str
    scenarioId: str | None
    seed: int
    expectedService: str | None
    expectedCategory: str | None
    expectedIncident: bool


class EvaluationResult(BaseModel):
    id: str
    datasetVersion: str
    promptVersion: str
    startedAt: datetime
    completedAt: datetime
    cases: int
    detectionRecall: float
    falsePositiveRate: float
    rootCauseAccuracy: float
    evidenceValidity: float
    unsupportedClaimRate: float
    passed: bool
