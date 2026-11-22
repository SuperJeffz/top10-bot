@echo off
echo Stopping Top10 Bot...
taskkill /FI "WINDOWTITLE eq Top10 Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Top10 Frontend*" /T /F >nul 2>&1
taskkill /IM ollama.exe /F >nul 2>&1
echo Done.
timeout /t 3 >nul
