@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\pyinstaller --onefile --windowed --name FingerCounter ^
  --collect-all mediapipe ^
  --collect-all cv2 ^
  finger_counter_app.py
echo.
echo Executable created at dist\FingerCounter.exe
pause
