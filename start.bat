@echo off
title NoteShare
cd /d "%~dp0"
if not exist logs mkdir logs

echo.
echo  ╔══════════════════════════════════╗
echo  ║     NoteShare - Starting...     ║
echo  ╚══════════════════════════════════╝
echo.

:: Kill any existing python on port 5000
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5000') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: Activate venv and start app
call venv\Scripts\activate.bat
start /B python app.py > logs\app.log 2>&1

:: Wait for server
echo  Starting server, please wait...
timeout /t 4 /nobreak > nul

:: Open in Edge (supports PWA on localhost without HTTPS)
echo  Opening NoteShare in browser...
start msedge --app=http://localhost:5000 --start-maximized

echo.
echo  ╔══════════════════════════════════╗
echo  ║  NoteShare is running!           ║
echo  ║  URL: http://localhost:5000      ║
echo  ║  Press any key to STOP          ║
echo  ╚══════════════════════════════════╝
pause > nul

taskkill /F /IM python.exe >nul 2>&1
echo  Server stopped. Goodbye!
timeout /t 2 /nobreak > nul
