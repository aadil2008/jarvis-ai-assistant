@echo off
cd /d "%~dp0"
set "JARVIS_PY=py -3.12"
%JARVIS_PY% --version >nul 2>&1
if errorlevel 1 set "JARVIS_PY=py -3"
%JARVIS_PY% -c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] <= (3,13) else 1)"
if errorlevel 1 goto error
%JARVIS_PY% -m venv .venv
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
".venv\Scripts\python.exe" setup_assistant.py
if errorlevel 1 goto error
echo Run Start_Jarvis.bat after setup succeeds.
pause
exit /b 0
:error
echo Setup incomplete. Use Python 3.11-3.13 and check the message above. Re-run setup to retry.
pause
exit /b 1
