@echo off
cd /d "%~dp0"
if not exist logs mkdir logs
call venv\Scripts\activate.bat
start /B python app.py > logs\app.log 2>&1
timeout /t 3 /nobreak > nul
start http://localhost:5000
echo NoteShare is running at http://localhost:5000
echo Close this window to stop the server.
pause
taskkill /F /IM python.exe > nul 2>&1
