@echo off
setlocal
set "ROOT=%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo Python Launcher was not found. Install 64-bit Python 3.10 or newer from python.org,
    echo select "Add Python to PATH", then run this file again.
    exit /b 1
)

echo Creating or updating the AirKeys virtual environment...
py -3 -m venv "%ROOT%.venv"
if errorlevel 1 exit /b 1

"%ROOT%.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%ROOT%.venv\Scripts\python.exe" -m pip install -r "%ROOT%requirements.txt"
if errorlevel 1 exit /b 1

echo.
echo Checking this computer's Bluetooth support...
"%ROOT%.venv\Scripts\python.exe" "%ROOT%cli.py" check
exit /b %errorlevel%
