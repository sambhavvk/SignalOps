param([ValidateRange(1,3600)][int]$DurationSeconds = 60)
$end = (Get-Date).AddSeconds($DurationSeconds)
while ((Get-Date) -lt $end) {
  $key = "manual-$([guid]::NewGuid().ToString('N'))"
  Invoke-RestMethod -Method Post -Uri 'http://localhost:8100/api/v1/orders' -Headers @{ 'Idempotency-Key'=$key; 'X-Correlation-ID'=$key } -ContentType 'application/json' -Body '{"productId":"sku-signal-lamp","quantity":1,"amount":49.0}' | Out-Null
  Start-Sleep -Seconds 2
}
