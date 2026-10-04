param([ValidateSet('recorded','phone')][string]$Mode = 'phone')
$ErrorActionPreference = 'Stop'
$vbName = "demo-$Mode"
$vbConfig = Get-Content (Join-Path $PSScriptRoot "runtime\profiles\$vbName.json") -Raw | ConvertFrom-Json
$vbSecure = (Get-Content (Join-Path $PSScriptRoot "runtime\profiles\$vbName-operator.dpapi") -Raw).Trim() | ConvertTo-SecureString
$vbToken = [System.Net.NetworkCredential]::new('', $vbSecure).Password
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8200/operator/shutdown -Headers @{'X-VB-Operator'=$vbToken} -TimeoutSec 5 | Out-Null
for ($vbTry=0; $vbTry -lt 60; $vbTry++) {
    Start-Sleep -Milliseconds 500
    $vbState = Get-Content (Join-Path $vbConfig.runtime_dir 'integrated-process.json') -Raw | ConvertFrom-Json
    if ($vbState.state -eq 'stopped') { Write-Output 'Bob, Stuart, and the local model stopped. Demo history retained.'; return }
}
throw 'Shutdown is still pending. Check integrated.stderr.log.'
