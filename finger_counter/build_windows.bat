@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\python -c "from finger_counter_app import download_model; import sys; sys.exit(0 if download_model() else 1)" || (echo Failed to download hand model & exit /b 1)
.venv\Scripts\python -m pip install pyinstaller
.venv\Scripts\pyinstaller --onefile --windowed --name FingerCounter ^
  --collect-all mediapipe ^
  --collect-all cv2 ^
  --add-data "models\hand_landmarker.task;models" ^
  finger_counter_app.py
echo.
echo Executable created at dist\FingerCounter.exe
pause
