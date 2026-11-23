@echo off
REM =========================================================
REM  build_windows.bat — Build Anything to PDF for Windows
REM  Run this script on a Windows machine with Python installed.
REM =========================================================

echo [1/4] Creating virtual environment...
python -m venv .venv
call .venv\Scripts\activate

echo [2/4] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo [3/4] Running tests...
pip install pytest
set PYTHONPATH=src
pytest tests\ -v
if errorlevel 1 (
    echo Tests FAILED. Aborting build.
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
