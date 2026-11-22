@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python tidak ditemukan. Instal Python 3.10+ dari https://python.org
  echo lalu jalankan setup.bat lagi.
  pause
  exit /b 1
)
python scripts\setup.py %*
pause
