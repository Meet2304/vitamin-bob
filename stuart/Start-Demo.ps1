param([switch]$Interactive,[int]$Lines=3,[int]$Port=18200,[int]$MockPort=18100)
$ErrorActionPreference = 'Stop'
$vbModuleRoot = $PSScriptRoot
$vbPython = Join-Path $vbModuleRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $vbPython)) { throw 'Create stuart/.venv and install stuart/requirements.txt first. See README.md.' }
foreach ($vbPort in @($Port,$MockPort)) {
    $vbProbe = [System.Net.Sockets.TcpClient]::new()
    try { $vbConnect = $vbProbe.ConnectAsync('127.0.0.1',$vbPort); $vbConnect.Wait(500) | Out-Null } catch { }
    $vbOccupied = $vbProbe.Connected
    $vbProbe.Dispose()
    if ($vbOccupied) { throw "Port $vbPort is already in use. Stop the previous demo or choose other ports." }
}
$vbRuntime = Join-Path $vbModuleRoot 'runtime'
New-Item -ItemType Directory -Path $vbRuntime -Force | Out-Null
$env:VB_DATA_DIR = Join-Path $vbRuntime 'demo-data'
$env:VB_BOB_URL = "http://127.0.0.1:$MockPort"
$env:VB_STUART_URL = "http://127.0.0.1:$Port"
$env:VB_SIM_LINES = if ($Interactive) { '1' } else { [string]$Lines }
$env:VB_SIM_MODE = if ($Interactive) { 'interactive' } else { 'scripted' }
$env:VB_SYNC_TRANSPORT = 'loopback'
$env:VB_ANDROID_ENABLED = '0'
$env:VB_OPERATOR_TOKEN = [guid]::NewGuid().ToString('N')
$vbArguments = @('-m','stuart','fake-bob','--port',"$MockPort")
$vbMock = Start-Process -FilePath $vbPython -ArgumentList $vbArguments -WorkingDirectory $vbModuleRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $vbRuntime 'mock.stdout.log') -RedirectStandardError (Join-Path $vbRuntime 'mock.stderr.log') -PassThru
$vbService = Start-Process -FilePath $vbPython -ArgumentList @('-m','stuart','serve','--port',"$Port") -WorkingDirectory $vbModuleRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $vbRuntime 'stuart.stdout.log') -RedirectStandardError (Join-Path $vbRuntime 'stuart.stderr.log') -PassThru
@{ mock=$vbMock.Id; stuart=$vbService.Id; port=$Port; mockPort=$MockPort; started=(Get-Date).ToString('o'); shutdownToken=$env:VB_OPERATOR_TOKEN } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $vbRuntime 'demo-processes.json')
Write-Output "Stuart console: http://127.0.0.1:$Port"
Write-Output "Fake Bob events: http://127.0.0.1:$MockPort/mock/events"
Write-Output 'Simulation only. No phone calls or over-air SMS are enabled.'
