$ErrorActionPreference = 'Stop'
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
docker compose config --quiet
Write-Host 'SignalOps configuration is ready.'
