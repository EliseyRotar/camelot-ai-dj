# Camelot AI DJ - Dev Launcher (browser mode, no Tauri build required)
# Runs the Python sidecar in the FOREGROUND so Ctrl+C cleanly stops everything.
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Sidecar = Join-Path $Root 'sidecar'
$VenvPython = Join-Path $Sidecar '.venv\Scripts\python.exe'
$Python = if (Test-Path $VenvPython) { $VenvPython } else { 'python' }

Write-Host "[camelot] Starting sidecar (foreground): $Python main.py" -ForegroundColor Cyan
Write-Host "[camelot] UI will open at http://127.0.0.1:8765/ once the server is up." -ForegroundColor Cyan
Write-Host "[camelot] Press Ctrl+C in this window to stop the app." -ForegroundColor Yellow
Write-Host ""

# Open the browser after a short delay (async, does not block the sidecar)
Start-Job -ScriptBlock {
    param($url)
    Start-Sleep -Seconds 4
    Start-Process $url
} -ArgumentList 'http://127.0.0.1:8765/' | Out-Null

# Run the sidecar in THIS process group so Ctrl+C propagates and Wait-Process blocks.
$proc = Start-Process -FilePath $Python -ArgumentList 'main.py' -WorkingDirectory $Sidecar -PassThru -NoNewWindow
try {
    Wait-Process -Id $proc.Id
} catch {
    # Ctrl+C throws a terminating error; make sure the child is gone.
    try { Stop-Process -Id $proc.Id -Force } catch {}
}