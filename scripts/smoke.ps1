param([int]$ApiPort = 18080, [int]$MetricsPort = 18081)
$ErrorActionPreference = 'Stop'
$api = "http://127.0.0.1:$ApiPort/api/sentiment"
$management = "http://127.0.0.1:$MetricsPort/actuator"
$rows = [ordered]@{
  hello = 'positive'
  horrible = 'negative'
  meeting = 'neutral'
  'отлично' = 'positive'
  'ужасно' = 'negative'
  'сегодня' = 'neutral'
  xyz = 'neutral'
}
foreach ($sample in $rows.Keys) {
  $encoded = [Uri]::EscapeDataString($sample)
  $response = Invoke-WebRequest -Uri "${api}?text=$encoded"
  "GET /api/sentiment?text=$sample -> $($response.StatusCode) $($response.Content)"
  if (($response.Content | ConvertFrom-Json).sentiment -ne $rows[$sample]) {
    throw "Unexpected prediction for $sample"
  }
}
$cases = [ordered]@{
  missing = $api
  blank = "${api}?text=%20"
  oversized = ("${api}?text=" + ('x' * 2049))
}
foreach ($case in $cases.Keys) {
  $response = Invoke-WebRequest -Uri $cases[$case] -SkipHttpErrorCheck
  "GET /api/sentiment ($case) -> $($response.StatusCode)"
  if ($response.StatusCode -ne 400) { throw "Expected HTTP 400 for $case" }
}
$health = Invoke-RestMethod -Uri "$management/health/readiness"
"GET /actuator/health/readiness -> $($health | ConvertTo-Json -Compress)"
if ($health.status -ne 'UP') { throw 'Readiness check failed' }
$metrics = (Invoke-WebRequest -Uri "$management/prometheus").Content
$metrics -split "`n" | Where-Object { $_ -match '^sentiment_predictions_total' }
if ($metrics -notmatch 'http_server_requests_seconds_bucket' -or $metrics -notmatch 'sentiment_predictions_total') {
  throw 'Required metrics missing'
}
'PASS: HTTP contract and Prometheus exposition'
