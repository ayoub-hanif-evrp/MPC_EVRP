$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repo

Add-Type -TypeDefinition @'
using System.Runtime.InteropServices;
public static class CampaignPower {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint flags);
}
'@

$powerState = [CampaignPower]::SetThreadExecutionState(0x80000001)
if ($powerState -eq 0) {
    throw 'Could not prevent system sleep during the final holdout.'
}

$log = Join-Path $repo 'results/final_study/resume.log'
try {
    python -u -m scripts.run_final_holdout 2>&1 | Tee-Object -FilePath $log
    if ($LASTEXITCODE -ne 0) {
        throw "Final holdout stopped with exit code $LASTEXITCODE. Check preserved failure evidence before resuming."
    }

    python -m scripts.analyze_final_holdout 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Final analysis failed with exit code $LASTEXITCODE."
    }

    python -m scripts.render_final_paper 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Paper rendering failed with exit code $LASTEXITCODE."
    }

    'Final holdout, audit, and paper rendering completed. Review results/final_study/paper/RESULTS.md.' |
        Tee-Object -FilePath $log -Append
}
finally {
    [void][CampaignPower]::SetThreadExecutionState(0x80000000)
}
