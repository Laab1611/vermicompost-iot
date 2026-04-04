Set-StrictMode -Version Latest

$allowed = @("smoke", "load", "stress")
$scenario = "smoke"
if ($args.Count -gt 0 -and $args[0]) {
    $scenario = $args[0].ToLowerInvariant()
}
if (-not ($allowed -contains $scenario)) {
    Write-Error "Escenario invalido. Usa: smoke, load o stress"
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Split-Path -Parent (Split-Path -Parent $scriptDir)
$Plan = Join-Path $scriptDir "vermicompost-backend.jmx"
$Properties = Join-Path $scriptDir "profiles/$scenario.properties"
$DataDir = Join-Path $scriptDir "data"
$ResultsRoot = Join-Path $repoDir "performance-tests/results"
$Timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ResultsDir = Join-Path $ResultsRoot "$scenario/$Timestamp"
$CasesDir = Join-Path $ResultsDir "cases"
$CaseReportsDir = Join-Path $ResultsDir "case-reports"
$JtlFile = Join-Path $ResultsDir "run.jtl"
$ReportDir = Join-Path $ResultsDir "html-report"

New-Item -ItemType Directory -Path $ResultsDir -Force | Out-Null
New-Item -ItemType Directory -Path $CasesDir -Force | Out-Null
New-Item -ItemType Directory -Path $CaseReportsDir -Force | Out-Null
if (Test-Path $ReportDir) {
    Remove-Item -Recurse -Force $ReportDir
}

Push-Location $repoDir
try {
    jmeter -n -t $Plan -q $Properties -Jdata_dir=$DataDir -Jresults_base_dir=$CasesDir -l $JtlFile -e -o $ReportDir

    $caseOutputs = @(
        @{ Name = "ingestion-valid"; Jtl = (Join-Path $CasesDir "ingestion-valid.jtl") },
        @{ Name = "ingestion-backlog-30m"; Jtl = (Join-Path $CasesDir "ingestion-backlog-30m.jtl") },
        @{ Name = "query-summary"; Jtl = (Join-Path $CasesDir "query-summary.jtl") },
        @{ Name = "query-historico"; Jtl = (Join-Path $CasesDir "query-historico.jtl") },
        @{ Name = "twins-overview"; Jtl = (Join-Path $CasesDir "twins-overview.jtl") },
        @{ Name = "twins-list"; Jtl = (Join-Path $CasesDir "twins-list.jtl") }
    )

    foreach ($case in $caseOutputs) {
        if (Test-Path $case.Jtl) {
            $caseReportDir = Join-Path $CaseReportsDir $case.Name
            if (Test-Path $caseReportDir) {
                Remove-Item -Recurse -Force $caseReportDir
            }
            jmeter -g $case.Jtl -o $caseReportDir
        }
    }
}
finally {
    Pop-Location
}

Write-Host "Perfil ejecutado: $scenario"
Write-Host "JTL: $JtlFile"
Write-Host "Reporte: $ReportDir"
Write-Host "Casos (JTL): $CasesDir"
Write-Host "Reportes por caso: $CaseReportsDir"
