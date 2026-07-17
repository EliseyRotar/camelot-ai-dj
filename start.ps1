# Camelot AI DJ - Dev Launcher (browser mode, no Tauri build required)
# Spawns the Python sidecar then opens the UI at http://127.0.0.1:8765
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Sidecar = Join-Path $Root 'sidecar'
$VenvPython = Join-Path $Sidecar '.venv\Scripts\python.exe'
$Python = if (Test-Path $VenvPython) { $VenvPython } else { 'python' }

Write-Host "[camelot] Starting sidecar: $Python sidecar/main.py" -ForegroundColor Cyan
$proc = Start-Process -FilePath $Python -ArgumentList 'main.py' -WorkingDirectory $Sidecar -PassThru -WindowStyle Normal
Start-Sleep -Seconds 3

Write-Host "[camelot] Opening browser at http://127.0.0.1:8765/" -ForegroundColor Cyan
Start-Process 'http://127.0.0.1:8765/'

Write-Host ""
Write-Host " Camelot AI DJ is running." -ForegroundColor Green
Write-Host " UI:        http://127.0.0.1:8765/" -ForegroundColor Green
Write-Host " Sidecar PID: $($proc.Id) (close this window to stop)" -ForegroundColor Green
Write-Host ""

# Keep this window open until the sidecar exits
if ($proc) { Wait-Process -Id $proc.Id }