from fastapi.testclient import TestClient

from signalops import main
from signalops.store import StateStore


def test_scenario_incident_diagnosis_and_recovery(tmp_path, monkeypatch):
    main.store = StateStore(str(tmp_path / "state.json"))

    async def no_fault_propagation(*args, **kwargs):
        return None

    monkeypatch.setattr(main, "propagate_fault", no_fault_propagation)
    client = TestClient(main.app)
    headers = {"X-Fault-Control-Token": "signalops-local-demo"}

    started = client.post("/api/v1/scenarios/runs", headers=headers, json={"scenarioId": "F-04", "ttlSeconds": 180})
    assert started.status_code == 201
    payload = started.json()

    detail = client.get(f"/api/v1/incidents/{payload['incidentId']}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "open"
    assert len(detail.json()["evidence"]) == 4

    diagnosis = client.post(f"/api/v1/incidents/{payload['incidentId']}/diagnoses")
    assert diagnosis.status_code == 202
    supplied = {item["id"] for item in detail.json()["evidence"]}
    cited = {ref for claim in diagnosis.json()["claims"] for ref in claim["evidenceIds"]}
    assert cited <= supplied
    assert all(action["risk"] == "read_only" for action in diagnosis.json()["recommendedActions"])

    cleared = client.delete(f"/api/v1/scenarios/runs/{payload['run']['id']}", headers=headers)
    assert cleared.status_code == 204
    assert client.get(f"/api/v1/incidents/{payload['incidentId']}").json()["status"] == "resolved"


def test_invalid_scenario_is_rejected(tmp_path):
    main.store = StateStore(str(tmp_path / "state.json"))
    response = TestClient(main.app).post(
        "/api/v1/scenarios/runs",
        headers={"X-Fault-Control-Token": "signalops-local-demo"},
        json={"scenarioId": "shell-command", "ttlSeconds": 180},
    )
    assert response.status_code == 422
