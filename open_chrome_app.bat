@echo off
title NoteShare
cd /d "%~dp0"
if not exist logs mkdir logs

echo Starting NoteShare...

:: Kill existing on port 5000
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr :5000') do (
    taskkill /F /PID %%a >nul 2>&1
)

:: Start server
call venv\Scripts\activate.bat
start /B python app.py > logs\app.log 2>&1
timeout /t 4 /nobreak > nul

:: Try Chrome app mode first
set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
set CHROME2="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
set EDGE="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
set EDGE2="C:\Program Files\Microsoft\Edge\Application\msedge.exe"

if exist %CHROME% (
    echo Opening in Chrome app mode...
    start "" %CHROME% --app=http://localhost:5000 --window-size=1280,800 --no-first-run --app-icon="%~dp0static\icons\icon-256.png"
    goto :done
)
if exist %CHROME2% (
    echo Opening in Chrome app mode...
    start "" %CHROME2% --app=http://localhost:5000 --window-size=1280,800 --no-first-run --app-icon="%~dp0static\icons\icon-256.png"
    goto :done
)
if exist %EDGE% (
    echo Opening in Edge app mode...
    start "" %EDGE% --app=http://localhost:5000 --window-size=1280,800
    goto :done
)
if exist %EDGE2% (
    echo Opening in Edge app mode...
    start "" %EDGE2% --app=http://localhost:5000 --window-size=1280,800
    goto :done
)

:: Fallback - just open in default browser
echo Opening in default browser...
start http://localhost:5000

:done
echo.
echo NoteShare is running at http://localhost:5000
echo Close this window to stop the server.
echo.
pause
taskkill /F /IM python.exe >nul 2>&1
