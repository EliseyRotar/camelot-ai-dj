@echo off
REM Camelot AI DJ - Dev Launcher (browser mode, no Tauri build required)
REM Runs the Python sidecar in the FOREGROUND so Ctrl+C cleanly stops everything.
setlocal
set ROOT=%~dp0
set SIDECAR=%ROOT%sidecar
set PYTHON=%SIDECAR%\.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

echo [camelot] Starting sidecar (foreground): %PYTHON% main.py
echo [camelot] UI will open at http://127.0.0.1:8765/ once the server is up.
echo [camelot] Press Ctrl+C in this window to stop the app.
echo.

REM Open the browser after 4 seconds (does not block the sidecar)
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start "" http://127.0.0.1:8765/"

REM Run the sidecar in THIS console so Ctrl+C propagates and the window stays open.
cd /d "%SIDECAR%"
"%PYTHON%" main.py
endlocal