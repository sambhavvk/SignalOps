from datetime import timedelta

import pytest

from signalops.domain import Claim, Diagnosis, Recommendation, ScenarioRun, utcnow
from signalops.engine import diagnose, evidence_for, evaluation_cases, incident_for


@pytest.mark.parametrize("scenario_id", ["F-01", "F-02", "F-03", "F-04"])
def test_diagnosis_only_cites_supplied_evidence(scenario_id):
    now = utcnow()
    incident = incident_for(ScenarioRun(id="run_test", scenarioId=scenario_id, startedAt=now, expiresAt=now + timedelta(minutes=3)))
    result = diagnose(incident)
    result.validate_references(incident.evidence)
    assert result.rootCause is not None
    assert all(action.risk == "read_only" for action in result.recommendedActions)


def test_unknown_citation_is_rejected():
    now = utcnow()
    incident = incident_for(ScenarioRun(id="run_test", scenarioId="F-02", startedAt=now, expiresAt=now + timedelta(minutes=3)))
    result = diagnose(incident)
    result.claims.append(Claim(text="unsupported", evidenceIds=["ev_missing"]))
    with pytest.raises(ValueError):
        result.validate_references(incident.evidence)


def test_dataset_has_twelve_positive_and_four_negative_cases():
    cases = evaluation_cases()
    assert sum(case.expectedIncident for case in cases) == 12
    assert sum(not case.expectedIncident for case in cases) == 4
