@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo  Chess Registration Verifier Setup
echo ==========================================

:: Check if Python 3.13 is available via py launcher
py -3.13 --version >nul 2>&1
if !errorlevel! equ 0 (
    echo [INFO] Detected Python 3.13. Using it to create virtual environment...
    set PYTHON_CMD=py -3.13
) else (
    :: Check if default python is available
    python --version >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] Python is not installed or not in your PATH.
        echo Please install Python 3.10+ (preferably Python 3.13) and try again.
        pause
        exit /b 1
    )
    echo [INFO] Using system default python...
    set PYTHON_CMD=python
)

:: Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo [INFO] Creating Python virtual environment...
    !PYTHON_CMD! -m venv .venv
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

:: Activate virtual environment
echo [INFO] Activating virtual environment...
call .venv\Scripts\activate.bat

:: Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

:: Install dependencies
echo [INFO] Installing requirements from requirements.txt...
pip install -r requirements.txt
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:: Install Playwright Chromium browser
echo [INFO] Installing Playwright Chromium browser...
playwright install chromium
if !errorlevel! neq 0 (
    echo [ERROR] Failed to install Playwright browser dependencies.
    pause
    exit /b 1
)

:: Run the application
echo [INFO] Starting the Chess Verification App...
python app.py

pause
