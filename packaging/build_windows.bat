@echo off
REM =========================================================
REM  build_windows.bat — Build Anything to PDF for Windows 11
REM
REM  Just double-click this file, or run it from anywhere.
REM  It will find the project root automatically.
REM =========================================================

REM Always run from the project root (parent of this script's folder)
cd /d "%~dp0.."
echo Working directory: %CD%
echo.

REM ----------------------------------------------------------
REM [1/4] Virtual environment
REM ----------------------------------------------------------
echo [1/4] Creating virtual environment...
python -m venv .venv
if errorlevel 1 (
    echo ERROR: Could not create virtual environment.
    echo Make sure Python 3.10+ is installed and on your PATH.
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat
echo Virtual environment ready.
echo.

REM ----------------------------------------------------------
REM [2/4] Install dependencies
REM   - Use "python -m pip" instead of "pip" to avoid Device
REM     Guard blocking the pip.exe binary on managed machines.
REM   - Do NOT upgrade pip (avoids replacing pip.exe with a
REM     freshly downloaded binary that may be blocked).
REM   - Install everything in one shot, including pytest.
REM ----------------------------------------------------------
echo [2/4] Installing dependencies (this may take a few minutes)...
python -m pip install --no-warn-script-location -r requirements.txt -r requirements-dev.txt
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    echo If you see a Device Guard or policy error, ask your IT
    echo administrator to whitelist Python pip installs, or use
    echo a personal (non-managed) Windows machine.
    pause
    exit /b 1
)
echo Dependencies installed.
echo.

REM ----------------------------------------------------------
REM [3/4] Run tests
REM   - Use "python -m pytest" to avoid running pytest.exe
REM ----------------------------------------------------------
echo [3/4] Running automated tests...
set PYTHONPATH=src
python -m pytest tests\ -v
if errorlevel 1 (
    echo.
    echo WARNING: Some tests failed. Review the output above.
    echo The build will continue, but please investigate failures
    echo before distributing the application.
    echo.
) else (
    echo All tests passed.
    echo.
)

REM ----------------------------------------------------------
REM [4/4] Build the executable
REM ----------------------------------------------------------
echo [4/4] Building Windows executable...
python -m PyInstaller packaging\anything_to_pdf.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed. See output above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  SUCCESS!
echo  Your executable is ready at:
echo    dist\AnythingToPDF.exe
echo.
echo  You can double-click it directly — no installation needed.
echo ============================================================
pause
