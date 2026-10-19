@echo off
setlocal
set "ROOT=%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python Launcher was not found.
    echo Install 64-bit Python 3.10 or newer from python.org, select "Add Python to PATH",
    echo then run this file again.
    exit /b 1
)

py -3 -c "import sys; print('Detected Python %d.%d.%d' %% sys.version_info[:3]); raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo ERROR: AirKeys requires Python 3.10 or newer. Install a supported version and retry.
    exit /b 1
)

echo Creating or updating the AirKeys virtual environment...
py -3 -m venv "%ROOT%.venv"
if errorlevel 1 (
    echo ERROR: Could not create .venv. Check disk permissions and the Python installation.
    exit /b 1
)

"%ROOT%.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Could not upgrade pip in .venv.
    exit /b 1
)
"%ROOT%.venv\Scripts\python.exe" -m pip install -r "%ROOT%requirements.txt"
if errorlevel 1 (
    echo ERROR: Dependency installation failed. Check your internet connection and requirements.txt.
    exit /b 1
)

echo.
echo Checking this computer's Bluetooth support...
"%ROOT%.venv\Scripts\python.exe" "%ROOT%cli.py" check
exit /b %errorlevel%
