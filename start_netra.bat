@echo off
title NETRA Surveillance System
cd /d "%~dp0"

echo ============================================================
echo   NETRA — Starting Surveillance Backend + Cloudflare Tunnel
echo ============================================================
echo.

:: Start NETRA backend in this window
start "NETRA Backend" cmd /k ".venv\Scripts\python.exe livedetector.py"

:: Wait for backend to start
echo Waiting for NETRA to start on port 5001...
timeout /t 10 /nobreak >nul

:: Start Cloudflare tunnel in a second window and capture the URL
start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://localhost:5001 2>&1 | tee %TEMP%\cf_url.log"

echo.
echo ============================================================
echo   Both windows are now open:
echo     1) NETRA Backend  - keep this running
echo     2) Cloudflare Tunnel - your public URL will appear here
echo ============================================================
echo.
echo Look for a line like:
echo   https://xxxx-xxxx-xxxx.trycloudflare.com
echo in the Cloudflare Tunnel window.
echo.
echo Paste that URL into the NETRA mobile app Settings tab.
echo ============================================================
pause
