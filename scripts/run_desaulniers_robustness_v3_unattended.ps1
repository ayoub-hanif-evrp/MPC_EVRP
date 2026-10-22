param([double]$MaxHours = 12)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
$log = Join-Path $root 'results/desaulniers/robustness_v3/resume.log'
$started = Get-Date

for ($scenario = 1; $scenario -le 90; $scenario++) {
    if ($MaxHours -gt 0 -and ((Get-Date) - $started).TotalHours -ge $MaxHours) {
        "Paused at a scenario boundary after $MaxHours hours." |
            Tee-Object -FilePath $log -Append
        break
    }
    "Starting scenario prefix $scenario/90 at $(Get-Date -Format o)" |
        Tee-Object -FilePath $log -Append
    python -u -m scripts.run_desaulniers_robustness_v3 --scenario-limit $scenario 2>&1 |
        Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        "Stopped after a worker or audit failure; inspect failures and resume.log." |
            Tee-Object -FilePath $log -Append
        exit $LASTEXITCODE
    }
}

python -m scripts.analyze_desaulniers_robustness --v3 2>&1 |
    Tee-Object -FilePath $log -Append
exit $LASTEXITCODE
