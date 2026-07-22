from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock

from .domain import EvaluationResult, Incident, ScenarioRun


class StateStore:
    """Small durable adapter for the local demo; writes are atomic and process-safe via one worker."""

    def __init__(self, path: str | None = None):
        self.path = Path(path or os.getenv("SIGNALOPS_STATE_PATH", "/data/state.json"))
        self.lock = RLock()
        self.incidents: dict[str, Incident] = {}
        self.runs: dict[str, ScenarioRun] = {}
        self.evaluations: dict[str, EvaluationResult] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.incidents = {x["id"]: Incident.model_validate(x) for x in raw.get("incidents", [])}
            self.runs = {x["id"]: ScenarioRun.model_validate(x) for x in raw.get("runs", [])}
            self.evaluations = {x["id"]: EvaluationResult.model_validate(x) for x in raw.get("evaluations", [])}
        except (OSError, ValueError, json.JSONDecodeError):
            self.incidents, self.runs, self.evaluations = {}, {}, {}

    def save(self) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps({
                "incidents": [x.model_dump(mode="json") for x in self.incidents.values()],
                "runs": [x.model_dump(mode="json") for x in self.runs.values()],
                "evaluations": [x.model_dump(mode="json") for x in self.evaluations.values()],
            }, indent=2), encoding="utf-8")
            tmp.replace(self.path)
