@echo off
setlocal
title Top10 Bot Launcher

set OLLAMA_MODELS=E:\ollama\models
set OLLAMA_EXE=C:\Users\jiepj\AppData\Local\Programs\Ollama\ollama.exe
set BACKEND=D:\shell\top10_free_bot\backend
set FRONTEND=D:\shell\top10_free_bot\frontend
set VENV=E:\top10bot\venv\Scripts\python.exe

echo [1/3] Starting Ollama...
start "Ollama Server" /min cmd /c "set OLLAMA_MODELS=E:\ollama\models && "%OLLAMA_EXE%" serve"
timeout /t 4 >nul

echo [2/3] Starting Backend (port 8000)...
start "Top10 Backend" /min cmd /c "cd /d %BACKEND% && "%VENV%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 4 >nul

echo [3/3] Starting Frontend (port 5173)...
start "Top10 Frontend" /min cmd /c "cd /d %FRONTEND% && npm run dev -- --port 5173"
timeout /t 6 >nul

echo Opening browser...
start "" http://localhost:5173

echo.
echo ============================================
echo  Top10 Bot is running
echo  Frontend : http://localhost:5173
echo  Backend  : http://127.0.0.1:8000/docs
echo ============================================
echo  Close the 3 minimized windows to stop it.
echo ============================================
timeout /t 8 >nul
endlocal
