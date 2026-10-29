@echo off
setlocal
cd /d "%~dp0backend"
if not exist ".env" copy ".env.example" ".env" >nul
echo Starting Food AI Intelligence backend from: %CD%
echo Backend API docs: http://127.0.0.1:8000/docs
py -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
echo.
echo Backend stopped. If an error appeared above, read it before retrying.
pause
