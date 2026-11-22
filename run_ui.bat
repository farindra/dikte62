@echo off
setlocal
set PYTHONUTF8=1
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Runtime belum siap. Jalankan setup.bat dulu.
  pause
  exit /b 1
)
echo Menyalakan Dikte62 di http://127.0.0.1:8777 ...
start "Dikte62 server" /min ".venv\Scripts\python.exe" scripts\server.py --port 8777
timeout /t 4 >nul
start "" http://127.0.0.1:8777
