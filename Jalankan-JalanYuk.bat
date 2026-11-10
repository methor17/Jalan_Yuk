@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo JalanYuk 2.5 - Python Trip Planner
echo Akses aplikasi setelah server hidup: http://localhost:8000
echo Tekan Ctrl+C untuk menghentikan server.
echo.
where py >nul 2>nul
if %errorlevel%==0 (
  py app.py
) else (
  python app.py
)
if errorlevel 1 (
  echo.
  echo Python tidak berhasil dijalankan. Instal Python 3.10+ dan coba lagi.
  pause
)
