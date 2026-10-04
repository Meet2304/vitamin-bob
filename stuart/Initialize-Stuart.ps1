param(
    [ValidatePattern('^[A-Za-z0-9_-]{1,16}$')][string]$Name = 'kevin',
    [ValidateSet('simulator','hardware')][string]$Mode = 'simulator',
    [Parameter(Mandatory=$true)][string]$DataDir,
    [string]$BobUrl = 'http://127.0.0.1:8100',
    [int]$Port = 8200,
    [string[]]$AllowedPhone = @(),
    [string]$CountryCode = '+91',
    [System.Management.Automation.PSCredential]$GatewayCredential
)
$ErrorActionPreference = 'Stop'
$vbRuntime = Join-Path $PSScriptRoot 'runtime'
$vbProfiles = Join-Path $vbRuntime 'profiles'
New-Item -ItemType Directory -Path $vbProfiles -Force | Out-Null
$vbConfig = Join-Path $vbProfiles "$Name.json"
if (Test-Path -LiteralPath $vbConfig) { throw 'Profile already exists. Edit its JSON to preserve its data paths and identity.' }
if (-not [System.IO.Path]::IsPathRooted($DataDir)) { throw 'DataDir must be absolute and match Bob.' }
if ($Mode -eq 'hardware' -and $AllowedPhone.Count -eq 0) { throw 'Specify at least one allowed test phone with -AllowedPhone.' }
$vbProfile = @{
    mode=$Mode; data_dir=[System.IO.Path]::GetFullPath($DataDir)
    runtime_dir=(Join-Path $vbRuntime "managed\$Name"); port=$Port; bob_url=$BobUrl
    hub_id=$Name; simulator_lines=3; calls_enabled=$false
    sms_send_enabled=($Mode -eq 'simulator'); sms_receive_enabled=$true
    allowed_phones=@($AllowedPhone); country_code=$CountryCode
    adb_path=(Join-Path $vbRuntime 'tools\platform-tools\adb.exe')
    daily_sms_cap=10; callback_max_attempts=1; sync_transport='loopback'; max_restarts=3
}
$vbProfile | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $vbConfig -Encoding UTF8
foreach ($vbKind in @('operator','webhook')) {
    $vbSecretPath = Join-Path $vbProfiles "$Name-$vbKind.dpapi"
    $vbRandom = [guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N')
    ConvertTo-SecureString -String $vbRandom -AsPlainText -Force | ConvertFrom-SecureString | Set-Content -LiteralPath $vbSecretPath
}
if ($null -ne $GatewayCredential) {
    $GatewayCredential.UserName | Set-Content -LiteralPath (Join-Path $vbRuntime 'smsgate-user.txt')
    $GatewayCredential.Password | ConvertFrom-SecureString | Set-Content -LiteralPath (Join-Path $vbRuntime 'smsgate-password.dpapi')
}
Write-Output "Created local profile: $vbConfig"
Write-Output 'Calls start disabled. Review calls_enabled and sms_send_enabled before a hardware demonstration.'
