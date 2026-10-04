param([string]$Config = (Join-Path $PSScriptRoot 'runtime\profiles\kevin.json'))
$ErrorActionPreference = 'Stop'
$vbConfigPath = (Resolve-Path -LiteralPath $Config).Path
$vbProfile = Get-Content -LiteralPath $vbConfigPath -Raw | ConvertFrom-Json
$vbPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
Push-Location -LiteralPath $PSScriptRoot
try { & $vbPython -c 'import sys; from stuart.runtime import load_profile; load_profile(sys.argv[1])' $vbConfigPath }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Profile validation failed.' }
$vbProbe = [System.Net.Sockets.TcpClient]::new()
try { $vbProbe.ConnectAsync('127.0.0.1',[int]$vbProfile.port).Wait(500) | Out-Null } catch { }
$vbOccupied = $vbProbe.Connected
$vbProbe.Dispose()
if ($vbOccupied) { throw 'Stuart port is occupied. Use Stop-Stuart.ps1 for the matching profile first.' }
$vbSecretRoot = Split-Path -Parent $vbConfigPath
$vbName = [System.IO.Path]::GetFileNameWithoutExtension($vbConfigPath)
function Read-VbSecret([string]$Path) {
    $vbSecure = (Get-Content -LiteralPath $Path -Raw).Trim() | ConvertTo-SecureString
    return [System.Net.NetworkCredential]::new('', $vbSecure).Password
}
$vbEnvNames = @('VB_OPERATOR_TOKEN','VB_SMS_WEBHOOK_TOKEN','VB_SMS_GATE_USER','VB_SMS_GATE_PASSWORD')
$vbPrevious = @{}
foreach ($vbKey in $vbEnvNames) { $vbPrevious[$vbKey] = [Environment]::GetEnvironmentVariable($vbKey,'Process') }
try {
    $env:VB_OPERATOR_TOKEN = Read-VbSecret (Join-Path $vbSecretRoot "$vbName-operator.dpapi")
    $env:VB_SMS_WEBHOOK_TOKEN = Read-VbSecret (Join-Path $vbSecretRoot "$vbName-webhook.dpapi")
    if ($vbProfile.mode -eq 'hardware') {
        $env:VB_SMS_GATE_USER = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'runtime\smsgate-user.txt') -Raw).Trim()
        $env:VB_SMS_GATE_PASSWORD = Read-VbSecret (Join-Path $PSScriptRoot 'runtime\smsgate-password.dpapi')
    }
    New-Item -ItemType Directory -Path $vbProfile.runtime_dir -Force | Out-Null
    $vbArgs = '-m stuart run --config "' + $vbConfigPath + '"'
    $vbProcess = Start-Process -FilePath $vbPython -ArgumentList $vbArgs -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $vbProfile.runtime_dir 'supervisor.stdout.log') -RedirectStandardError (Join-Path $vbProfile.runtime_dir 'supervisor.stderr.log')
    $vbStarted = $false
    for ($vbTry=0; $vbTry -lt 30; $vbTry++) {
        $vbProcess.Refresh()
        if ($vbProcess.HasExited) { throw 'Supervisor exited. Check supervisor.stderr.log in the profile runtime directory.' }
        try {
            $vbHealth = Invoke-RestMethod -Uri "http://127.0.0.1:$($vbProfile.port)/v1/health" -Headers @{'X-VB-Contract'='0.2'} -TimeoutSec 1
            if ($vbHealth.module -eq 'stuart') { $vbStarted=$true; break }
        } catch { }
        Start-Sleep -Milliseconds 300
    }
    if (-not $vbStarted) { throw 'Startup is still pending. Inspect the profile logs and run Get-StuartStatus.ps1.' }
    Write-Output "Stuart running: http://127.0.0.1:$($vbProfile.port)"
    & (Join-Path $PSScriptRoot 'Get-StuartStatus.ps1') -Config $vbConfigPath
} finally {
    foreach ($vbKey in $vbEnvNames) { [Environment]::SetEnvironmentVariable($vbKey,$vbPrevious[$vbKey],'Process') }
}
