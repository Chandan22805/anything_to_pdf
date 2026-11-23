# Anything to PDF — Windows PyInstaller spec
# Build from the PROJECT ROOT with:
#   pyinstaller packaging\anything_to_pdf.spec
# Do NOT run from inside the packaging\ folder.

import sys
from pathlib import Path

block_cipher = None

# Resolve paths relative to this spec file so the build works regardless
# of which directory PyInstaller is invoked from.
SPEC_DIR = Path(SPECPATH)          # directory containing this .spec file
PROJECT_ROOT = SPEC_DIR.parent     # one level up = project root
MAIN_SCRIPT = str(PROJECT_ROOT / 'main.py')
SRC_PATH = str(PROJECT_ROOT / 'src')

a = Analysis(
    [MAIN_SCRIPT],
    pathex=[str(PROJECT_ROOT), SRC_PATH],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PIL',
        'PIL.Image',
        'PIL.ImageOps',
        'pypdf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineCore',
        'PySide6.QtMultimedia',
        'PySide6.QtSql',
        'matplotlib',
        'numpy',
        'scipy',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AnythingToPDF',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # Uncomment and add icon.ico to assets/
)
