@echo off
rem Double-click this once a year after FWP posts new harvest numbers.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" yearly_update.py
) else (
    python yearly_update.py
)
echo.
pause
