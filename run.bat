@echo off
setlocal enabledelayedexpansion

title Sift — Commercial Audit ^& Margin Triage Engine
color 0a

:: 1. Locate Python executable
set SCRIPT_DIR=%~dp0
set VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe

if exist "%VENV_PY%" (
    set TARGET_PY="%VENV_PY%"
) else (
    python --version >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set TARGET_PY=python
    ) else (
        color 0c
        echo ===============================================================================
        echo [ERROR] Sift runtime environment is not initialized!
        echo Please run 'setup.bat' first to install required dependencies and create .venv.
        echo ===============================================================================
        echo.
        pause
        exit /b 1
    )
)

:: 2. Verify backend launcher exists
if not exist "%SCRIPT_DIR%backend\run_desktop.py" (
    color 0c
    echo [ERROR] Launcher file '%SCRIPT_DIR%backend\run_desktop.py' was not found!
    echo Please verify you are running this script from the Sift root directory.
    pause
    exit /b 1
)

echo ===============================================================================
echo            STARTING SIFT COMMERCIAL AUDIT ^& MARGIN TRIAGE ENGINE
echo                Local-First ^& Air-Gapped Desktop Application
echo ===============================================================================
echo.
echo [*] Analytical Engine: In-Process DuckDB (4GB Memory Ceiling, Disk Spilling)
echo [*] Local IPC Gateway: http://127.0.0.1:8765
echo [*] Desktop Shell: Microsoft Edge / WebView2 Standalone App Window
echo.
echo Press Ctrl+C in this terminal to shut down Sift.
echo ===============================================================================
echo.

:: 3. Launch Desktop Harness
%TARGET_PY% "%SCRIPT_DIR%backend\run_desktop.py" %*

if %ERRORLEVEL% neq 0 (
    color 0c
    echo.
    echo [!] Sift desktop harness exited with status code %ERRORLEVEL%.
    echo If dependencies were missing, run 'setup.bat' to re-install.
    pause
)
