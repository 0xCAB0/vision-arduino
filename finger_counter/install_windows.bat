@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3.9+ is required. Install it from https://python.org and re-run. & exit /b 1)
python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
echo.
echo Setup complete. Launch the app with run_windows.bat
pause
