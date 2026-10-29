@echo off
setlocal
cd /d "%~dp0frontend"
echo Starting Food AI Intelligence frontend from: %CD%
if not exist node_modules (
  echo Dependencies not found. Run npm install first.
  pause
  exit /b 1
)
npm run dev
pause
