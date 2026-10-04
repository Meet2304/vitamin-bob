param([string]$Config = (Join-Path $PSScriptRoot 'runtime\profiles\kevin.json'))
$ErrorActionPreference = 'Stop'
$vbConfigPath = (Resolve-Path -LiteralPath $Config).Path
$vbProfile = Get-Content -LiteralPath $vbConfigPath -Raw | ConvertFrom-Json
$vbName = [System.IO.Path]::GetFileNameWithoutExtension($vbConfigPath)
$vbSecretPath = Join-Path (Split-Path -Parent $vbConfigPath) "$vbName-operator.dpapi"
$vbSecure = (Get-Content -LiteralPath $vbSecretPath -Raw).Trim() | ConvertTo-SecureString
$vbToken = [System.Net.NetworkCredential]::new('', $vbSecure).Password
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$($vbProfile.port)/operator/shutdown" -Headers @{'X-VB-Operator'=$vbToken} -TimeoutSec 5 | Out-Null
for ($vbTry=0; $vbTry -lt 100; $vbTry++) {
    Start-Sleep -Milliseconds 300
    $vbManifest = Join-Path $vbProfile.runtime_dir 'process.json'
    if (Test-Path -LiteralPath $vbManifest) {
        $vbState = Get-Content -LiteralPath $vbManifest -Raw | ConvertFrom-Json
        if ($vbState.state -eq 'stopped') { Write-Output 'Stuart stopped; queues and receipts preserved.'; exit 0 }
    }
}
Write-Output 'Shutdown requested. Check Get-StuartStatus.ps1 for cleanup completion.'
