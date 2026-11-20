[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ResultsFile
)

$resolvedResults = Resolve-Path -LiteralPath $ResultsFile -ErrorAction Stop
$samples = @(Import-Csv -LiteralPath $resolvedResults.Path)
$httpSamples = @($samples | Where-Object { -not [string]::IsNullOrWhiteSpace($_.URL) })

if ($httpSamples.Count -eq 0) {
    throw "No HTTP samples found in $ResultsFile"
}

$failedSamples = @($httpSamples | Where-Object { $_.success -ne "true" })
$failurePercent = 100.0 * $failedSamples.Count / $httpSamples.Count
Write-Output ("HTTP samples: {0}; failed: {1}; failure rate: {2:N2}%" -f $httpSamples.Count, $failedSamples.Count, $failurePercent)

if ($failedSamples.Count -gt 0) {
    throw "One or more HTTP samples failed an assertion or request"
}
if ($failurePercent -ge 1.0) {
    throw "HTTP failure rate must remain below 1%"
}

$requiredLabels = @(
    "GET /api/events",
    "GET /api/events/{id}",
    "GET /api/events/{id}/availability",
    "POST /api/reservations"
)
if (@($httpSamples | Where-Object {
    $_.label -eq "POST /api/reservations" -and $_.responseCode -eq "201"
}).Count -gt 0) {
    $requiredLabels += "POST /api/reservations/{id}/confirm", "DELETE /api/reservations/{id}"
}
foreach ($label in $requiredLabels) {
    if (-not ($httpSamples | Where-Object { $_.label -eq $label } | Select-Object -First 1)) {
        throw "Missing HTTP sample for $label; the journey did not complete"
    }
}
