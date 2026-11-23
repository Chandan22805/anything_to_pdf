@echo off
REM =========================================================
REM  build_windows.bat — Build Anything to PDF for Windows
REM
REM  IMPORTANT: Run this script from the PROJECT ROOT folder.
REM  Example:
REM    cd C:\path\to\anything_to_pdf
REM    packaging\build_windows.bat
REM =========================================================

REM Change to the directory where this batch file lives, then go up one level
REM so we are always at the project root, regardless of where it was called from.
cd /d "%~dp0.."

echo Working directory: %CD%
echo.

echo [1/4] Creating virtual environment...
python -m venv .venv
call .venv\Scripts\activate.bat

echo [2/4] Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo [3/4] Running tests...
pip install pytest
set PYTHONPATH=src
pytest tests\ -v
if errorlevel 1 (
    echo.
    echo Tests FAILED. Fix the failures above before packaging.
    exit /b 1
)

echo [4/4] Building Windows executable with PyInstaller...
set PYTHONPATH=src
pyinstaller packaging\anything_to_pdf.spec --clean --noconfirm

echo.
echo ============================================================
echo  Build complete!
echo  Executable: dist\AnythingToPDF.exe
echo ============================================================
