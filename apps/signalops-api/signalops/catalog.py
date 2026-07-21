from .domain import ScenarioDefinition


SCENARIOS = {
    "F-01": ScenarioDefinition(
        id="F-01", name="Slow Orders database", targetService="orders-api",
        category="database_latency", description="Adds deterministic latency to Orders persistence.",
        injection="1,500 ms Orders database delay", expectedSignal="Slow database spans and elevated Orders p95",
    ),
    "F-02": ScenarioDefinition(
        id="F-02", name="Payment error surge", targetService="payments-api",
        category="application_failure", description="Returns HTTP 503 for 60% of authorisation requests.",
        injection="Seeded 60% payment HTTP 503", expectedSignal="Payment 5xx rate and failed Orders requests",
    ),
    "F-03": ScenarioDefinition(
        id="F-03", name="Inventory unavailable", targetService="inventory-api",
        category="service_unavailable", description="Fails readiness and rejects reservations.",
        injection="Inventory readiness and reservation failures", expectedSignal="Failed health checks and dependency spans",
    ),
    "F-04": ScenarioDefinition(
        id="F-04", name="Orders → Payments latency", targetService="orders-api",
        category="dependency_path_latency", description="Delays only the Orders-to-Payments dependency path.",
        injection="1,100 ms client-side dependency delay", expectedSignal="Slow client spans with normal Payments processing",
    ),
}

RUNBOOKS = {
    "F-01": "Compare Orders database spans with request duration. Inspect connection saturation and query plans. Do not restart or mutate data automatically.",
    "F-02": "Inspect Payments error events and recent deployment state. Confirm failures at the Payments server before attributing upstream order errors.",
    "F-03": "Verify Inventory readiness and dependency connectivity. Keep reservation retries bounded and avoid manual stock changes during investigation.",
    "F-04": "Compare Orders client spans with Payments server spans. If client duration is high while server duration is normal, investigate the dependency path, proxy, or network.",
}
