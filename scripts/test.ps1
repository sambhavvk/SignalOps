$ErrorActionPreference = 'Stop'
$env:PYTHONPATH = 'apps/signalops-api'
python -m pytest -q apps/signalops-api/tests
dotnet build services/orders-api --nologo
dotnet build services/payments-api --nologo
dotnet build services/inventory-api --nologo
Push-Location apps/web
try { npm test; npm run lint } finally { Pop-Location }
docker compose config --quiet
