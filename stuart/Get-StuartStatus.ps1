param([string]$Config = (Join-Path $PSScriptRoot 'runtime\profiles\kevin.json'))
$ErrorActionPreference = 'Stop'
$Config = (Resolve-Path -LiteralPath $Config).Path
Push-Location -LiteralPath $PSScriptRoot
try { & .\.venv\Scripts\python.exe -m stuart doctor --config $Config }
finally { Pop-Location }
