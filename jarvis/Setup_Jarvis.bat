@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo Setup finished. Double-click Start_Jarvis.bat to begin.
pause
exit /b 0
:error
echo Setup failed. Check that Python 3 is installed and try again.
pause
exit /b 1
