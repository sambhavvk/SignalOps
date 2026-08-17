$ErrorActionPreference = 'Stop'
$response = Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/v1/evaluations'
$response | ConvertTo-Json -Depth 8
if (-not $response.passed) { exit 1 }
