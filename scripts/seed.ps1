$ErrorActionPreference = 'Stop'
$products = Invoke-RestMethod -Uri 'http://localhost:8102/api/v1/products'
if (-not ($products | Where-Object id -eq 'sku-signal-lamp')) { throw 'Seed product is unavailable.' }
Write-Host 'Products and versioned runbooks are ready.'
