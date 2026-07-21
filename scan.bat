@echo off
cd /d "%~dp0"
python scan.py
echo.
start "" index.html
pause
