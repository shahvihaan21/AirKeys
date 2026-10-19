@echo off
set "ROOT=%~dp0.."
if exist "%ROOT%\.venv\Scripts\python.exe" (
  "%ROOT%\.venv\Scripts\python.exe" "%ROOT%\cli.py" on %*
) else (
  py -3 "%ROOT%\cli.py" on %*
)
pause
