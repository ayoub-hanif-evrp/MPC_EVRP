param([Parameter(Mandatory=$true)][int]$OwnerProcessId)

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class TargetedStudyPower {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint flags);
}
'@

$expires = (Get-Date).AddHours(12)
try {
    if ([TargetedStudyPower]::SetThreadExecutionState([uint32]2147483649) -eq 0) {
        throw 'Could not register the temporary system-awake request'
    }
    while ((Get-Date) -lt $expires) {
        $owner = Get-Process -Id $OwnerProcessId -ErrorAction SilentlyContinue
        if ($null -eq $owner -or $owner.ProcessName -ne 'python') { break }
        Start-Sleep -Seconds 5
    }
} finally {
    [void][TargetedStudyPower]::SetThreadExecutionState([uint32]2147483648)
}
