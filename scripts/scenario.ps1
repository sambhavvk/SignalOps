param([ValidateSet('F-01','F-02','F-03','F-04')][string]$Id = 'F-04', [ValidateRange(30,600)][int]$Ttl = 180)
$headers = @{ 'X-Fault-Control-Token' = $env:FAULT_CONTROL_TOKEN ?? 'signalops-local-demo' }
Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/scenarios/runs' -Headers $headers -ContentType 'application/json' -Body (@{ scenarioId=$Id; ttlSeconds=$Ttl } | ConvertTo-Json)
