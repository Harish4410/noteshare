@echo off
echo Stopping NoteShare...
taskkill /F /IM python.exe > nul 2>&1
echo Done!
timeout /t 2
