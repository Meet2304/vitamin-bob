param(
    [ValidateSet('recorded','phone')][string]$Mode = 'phone',
    [string]$AssetsDir = (Join-Path $PSScriptRoot '..\..\vitamin-bob-bob\data'),
    [string]$LlamaExe = (Join-Path $PSScriptRoot '..\..\llama.cpp\llama-server.exe'),
    [string]$ModelsDir = (Join-Path $PSScriptRoot '..\..\models')
)
$ErrorActionPreference = 'Stop'
$vbName = "demo-$Mode"
$vbConfig = Join-Path $PSScriptRoot "runtime\profiles\$vbName.json"
$vbPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$vbAssets = (Resolve-Path -LiteralPath $AssetsDir).Path
$vbLlama = (Resolve-Path -LiteralPath $LlamaExe).Path
$vbModels = (Resolve-Path -LiteralPath $ModelsDir).Path
if (-not (Test-Path -LiteralPath $vbConfig)) {
    $vbArguments = @{Name=$vbName; Mode='simulator'; DataDir=(Join-Path $PSScriptRoot "runtime\integrated-$Mode\data"); CountryCode='+1'}
    if ($Mode -eq 'phone') {
        $vbPhone = Get-Content (Join-Path $PSScriptRoot 'runtime\profiles\kevin.json') -Raw | ConvertFrom-Json
        $vbArguments.Mode = 'hardware'
        $vbArguments.AllowedPhone = @($vbPhone.allowed_phones)
    }
    & (Join-Path $PSScriptRoot 'Initialize-Stuart.ps1') @vbArguments
    $vbNew = Get-Content -LiteralPath $vbConfig -Raw | ConvertFrom-Json
    $vbNew.calls_enabled = ($Mode -eq 'phone')
    if ($Mode -eq 'phone') {
        $vbNew | Add-Member -NotePropertyName line_phone -NotePropertyValue $vbPhone.line_phone -Force
    }
    $vbNew.daily_sms_cap = 500
    $vbNew | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $vbConfig -Encoding UTF8
}
$vbProfile = Get-Content -LiteralPath $vbConfig -Raw | ConvertFrom-Json
foreach ($vbPort in @(8100,8200,8300)) {
    $vbSocket = [System.Net.Sockets.TcpClient]::new()
    try { $vbSocket.ConnectAsync('127.0.0.1',$vbPort).Wait(300) | Out-Null } catch { }
    $vbUsed = $vbSocket.Connected; $vbSocket.Dispose()
    if ($vbUsed) { throw "Port $vbPort is occupied. Stop the current integration instance before starting another." }
}
function Read-DemoSecret([string]$Path) {
    $vbSecure = (Get-Content -LiteralPath $Path -Raw).Trim() | ConvertTo-SecureString
    [System.Net.NetworkCredential]::new('', $vbSecure).Password
}
$vbSaved = @{}
foreach ($vbKey in @('VB_OPERATOR_TOKEN','VB_SMS_WEBHOOK_TOKEN','VB_SMS_GATE_USER','VB_SMS_GATE_PASSWORD')) {
    $vbSaved[$vbKey] = [Environment]::GetEnvironmentVariable($vbKey,'Process')
}
try {
    $env:VB_OPERATOR_TOKEN = Read-DemoSecret (Join-Path $PSScriptRoot "runtime\profiles\$vbName-operator.dpapi")
    $env:VB_SMS_WEBHOOK_TOKEN = Read-DemoSecret (Join-Path $PSScriptRoot "runtime\profiles\$vbName-webhook.dpapi")
    if ($Mode -eq 'phone') {
        $env:VB_SMS_GATE_USER = (Get-Content (Join-Path $PSScriptRoot 'runtime\smsgate-user.txt') -Raw).Trim()
        $env:VB_SMS_GATE_PASSWORD = Read-DemoSecret (Join-Path $PSScriptRoot 'runtime\smsgate-password.dpapi')
    }
    New-Item -ItemType Directory -Path $vbProfile.runtime_dir -Force | Out-Null
    $vbArgs = '-m stuart.integrated --mode ' + $Mode + ' --config "' + $vbConfig + '" --assets "' + $vbAssets + '" --llama "' + $vbLlama + '" --models "' + $vbModels + '"'
    $vbProcess = Start-Process -FilePath $vbPython -ArgumentList $vbArgs -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $vbProfile.runtime_dir 'integrated.stdout.log') -RedirectStandardError (Join-Path $vbProfile.runtime_dir 'integrated.stderr.log')
    Write-Output 'Loading local Gemma, Bob, and Stuart. First startup may take up to three minutes.'
    for ($vbTry=0; $vbTry -lt 180; $vbTry++) {
        $vbProcess.Refresh()
        if ($vbProcess.HasExited) { throw "Demo exited. Read $($vbProfile.runtime_dir)\integrated.stderr.log and model.log." }
        try {
            $vbState = Invoke-RestMethod http://127.0.0.1:8200/demo/state -TimeoutSec 1
            if ($vbState.model_ready) { Write-Output 'Dashboard ready: http://127.0.0.1:8100/dashboard'; return }
        } catch { }
        Start-Sleep -Seconds 1
    }
    throw 'Startup timed out. Inspect the demo logs before retrying.'
} finally {
    foreach ($vbKey in $vbSaved.Keys) { [Environment]::SetEnvironmentVariable($vbKey,$vbSaved[$vbKey],'Process') }
}
