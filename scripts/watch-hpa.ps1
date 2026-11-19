param([int]$DurationSeconds = 480)
$ErrorActionPreference = 'Stop'

function Kube {
    kubectl -n sentiment @args
    if ($LASTEXITCODE -ne 0) { throw "kubectl failed: $args" }
}

function Sample {
    $deployment = Kube get deployment sentiment -o json | ConvertFrom-Json
    $autoscaler = Kube get hpa sentiment -o json | ConvertFrom-Json
    $job = Kube get job sentiment-load --ignore-not-found -o json | ConvertFrom-Json
    $cpu = ($autoscaler.status.currentMetrics | Select-Object -First 1).resource.current.averageUtilization
    [pscustomobject]@{
        LocalTime = Get-Date -Format 'HH:mm:ss'
        Ready = [int]$deployment.status.readyReplicas
        Desired = [int]$autoscaler.status.desiredReplicas
        CPU = if ($null -eq $cpu) { 'unknown' } else { "$cpu%" }
        Completed = [int]$job.status.succeeded
    }
}

$initial = Sample
if ($initial.Ready -ne 3 -or $initial.CPU -eq 'unknown') {
    throw 'Wait for three ready app replicas and CPU data before starting.'
}
"Initial: ready=$($initial.Ready) desired=$($initial.Desired) cpu=$($initial.CPU)"
Kube apply -f k8s/load.yaml

$stop = (Get-Date).AddSeconds($DurationSeconds)
$up = $false
$down = $false
do {
    $sample = Sample
    "$($sample.LocalTime) ready=$($sample.Ready) desired=$($sample.Desired) cpu=$($sample.CPU) jobs-complete=$($sample.Completed)/3"
    if (!$up -and $sample.Ready -gt 3) {
        "PASS: scale-up 3 -> $($sample.Ready) ready"
        $up = $true
    }
    if ($up -and $sample.Completed -eq 3 -and $sample.Ready -eq 3 -and $sample.Desired -eq 3) {
        'PASS: scale-down -> 3 ready'
        $down = $true
        break
    }
    Start-Sleep -Seconds 8
} while ((Get-Date) -lt $stop)

Kube describe hpa sentiment
Kube logs -l job-name=sentiment-load --prefix --tail=8
if (!$up -or !$down) { throw 'Both scaling directions were not observed during this time window.' }
