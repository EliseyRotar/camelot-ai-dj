@echo off
REM Camelot AI DJ - Dev Launcher (browser mode, no Tauri build required)
REM Spawns the Python sidecar then opens the UI at http://127.0.0.1:8765
setlocal
set ROOT=%~dp0
set SIDECAR=%ROOT%sidecar
set PYTHON=%SIDECAR%\.venv\Scripts\python.exe
if not exist "%PYTHON%" set PYTHON=python

echo [camelot] Starting sidecar: %PYTHON% sidecar\main.py
start "camelot-sidecar" /D "%SIDECAR%" "%PYTHON%" main.py

timeout /t 3 /nobreak >nul
echo [camelot] Opening browser at http://127.0.0.1:8765/
start "" http://127.0.0.1:8765/

echo.
echo  Camelot AI DJ is running.
echo  UI:   http://127.0.0.1:8765/
echo  Close the sidecar console window to stop.
endlocal