@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" launch.py --voice
) else (
  py -3 launch.py --voice
)
pause
