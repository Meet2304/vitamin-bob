$ErrorActionPreference = 'Stop'
$vbRuntime = Join-Path $PSScriptRoot 'runtime'
$vbState = Join-Path $vbRuntime 'demo-processes.json'
if (Test-Path -LiteralPath $vbState) {
    $vbProcesses = Get-Content -LiteralPath $vbState -Raw | ConvertFrom-Json
    foreach ($vbPair in @(@{id=$vbProcesses.stuart;port=$vbProcesses.port},@{id=$vbProcesses.mock;port=$vbProcesses.mockPort})) {
        $vbProcessId = $vbPair.id
        $vbProcess = Get-Process -Id $vbProcessId -ErrorAction SilentlyContinue
        if ($vbProcesses.shutdownToken) {
            try { Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$($vbPair.port)/operator/shutdown" -Headers @{ 'X-VB-Operator'=$vbProcesses.shutdownToken } -TimeoutSec 2 | Out-Null } catch { }
            for ($vbWait=0; $vbWait -lt 20 -and (Get-Process -Id $vbProcessId -ErrorAction SilentlyContinue); $vbWait++) { Start-Sleep -Milliseconds 250 }
            $vbProcess = Get-Process -Id $vbProcessId -ErrorAction SilentlyContinue
        }
        if ($vbProcess -and $vbProcess.Path -eq (Join-Path $PSScriptRoot '.venv\Scripts\python.exe') -and $vbProcess.StartTime -ge ([datetime]$vbProcesses.started).AddSeconds(-10)) {
            if (Get-Process -Id $vbProcessId -ErrorAction SilentlyContinue) {
                # Venv's Windows launcher has a Python child; stop the verified project tree.
                & taskkill.exe /PID $vbProcessId /T /F | Out-Null
            }
        }
    }
}
