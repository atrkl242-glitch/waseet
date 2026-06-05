@echo off
title Waseet Local Server
echo ===================================================
echo   Starting Waseet Web Server...
echo   Open your browser at: http://127.0.0.1:5000
echo ===================================================
cd /d "%~dp0"
call .\venv\Scripts\activate
python app.py
pause
