@echo off
setlocal enabledelayedexpansion

title Project Sift — Environment Setup & Build
color 0b

echo ===============================================================================
echo                PROJECT SIFT: ENVIRONMENT SETUP & DEPENDENCY INSTALLER
echo        Local-First, Air-Gapped Commercial Audit & Margin Triage Desktop Engine
echo ===============================================================================
echo.

:: 1. Check Python installation
echo [*] Checking Python runtime...
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    py -3 --version >nul 2>&1
    if %ERRORLEVEL% neq 0 (
        color 0c
        echo [ERROR] Python 3 was not found on your system PATH!
        echo Please install Python 3.10 or 3.11 from https://www.python.org/downloads/
        echo Make sure to check the box "Add Python to PATH" during installation.
        echo.
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=py -3
    )
) else (
    set PYTHON_CMD=python
)

for /f "tokens=*" %%i in ('%PYTHON_CMD% --version') do set PY_VER=%%i
echo [OK] Found %PY_VER%

:: 2. Setup Virtual Environment
set VENV_DIR=%~dp0.venv
if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [*] Creating isolated virtual environment in .venv...
    %PYTHON_CMD% -m venv "%VENV_DIR%"
    if %ERRORLEVEL% neq 0 (
        color 0c
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully.
) else (
    echo [OK] Existing virtual environment found in .venv.
)

set VENV_PY="%VENV_DIR%\Scripts\python.exe"
set VENV_PIP="%VENV_DIR%\Scripts\pip.exe"

:: 3. Install Python Dependencies
echo.
echo [*] Installing / Verifying Python dependencies from backend\requirements.txt...
%VENV_PIP% install --upgrade pip --quiet
%VENV_PIP% install -r "%~dp0backend\requirements.txt"
if %ERRORLEVEL% neq 0 (
    color 0c
    echo [ERROR] Failed to install Python dependencies! Check your internet connection or wheels.
    pause
    exit /b 1
)
echo [OK] Python dependencies installed: duckdb, fastapi, uvicorn, pandas, pyarrow, pyzipper, openpyxl, pytest.

:: 4. Verify / Build Frontend Assets
echo.
echo [*] Checking frontend assets (React + Tailwind + Lucide)...
if exist "%~dp0src\dist\index.html" (
    echo [OK] Pre-compiled offline air-gapped frontend bundle found in src\dist.
) else (
    echo [!] Pre-compiled bundle not detected. Attempting build via npm...
    where npm >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo [*] Running npm install in src...
        cd /d "%~dp0src"
        call npm install
        echo [*] Running npm run build in src...
        call npm run build
        cd /d "%~dp0"
        if exist "%~dp0src\dist\index.html" (
            echo [OK] Frontend successfully built to src\dist.
        ) else (
            color 0e
            echo [WARNING] Frontend build did not generate src\dist\index.html. Fallback landing page will be served.
        )
    ) else (
        color 0e
        echo [WARNING] Node.js/npm not found on system. Sift will use existing pre-packaged assets or API mode.
    )
)

:: 5. Self-Diagnosis Smoke Test
echo.
echo [*] Running Sift self-diagnosis smoke test...
%VENV_PY% -c "from backend.storage import init_schema; from backend.app import app; print('    -> Backend storage and IPC router verified.')"
if %ERRORLEVEL% neq 0 (
    color 0c
    echo [ERROR] Sift self-diagnosis test failed!
    pause
    exit /b 1
)
echo [OK] Smoke test passed! All core analytical modules are intact.

echo.
echo ===============================================================================
echo                SETUP COMPLETED SUCCESSFULLY!
echo ===============================================================================
echo You can now launch Sift by double-clicking 'run.bat' or executing:
echo    .\run.bat
echo.
pause
