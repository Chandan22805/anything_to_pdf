# Anything to PDF

A lightweight desktop application that lets you combine images and existing PDF files into a single PDF document. Designed for non-technical users.

## Features

- Add **JPG, JPEG, PNG, WebP** images and **PDF** files
- **Drag and drop** files from your file manager
- Arrange files **left to right** — the leftmost file appears first in the output
- **Reorder** files by dragging cards horizontally
- Remove individual files
- **No intermediate files** — all processing is in memory
- Works **entirely offline** — no internet required
- **Sequential filename counter** (`combined1.pdf`, `combined2.pdf`, …)
- Full **error handling** with plain-language messages

## Supported Input Formats

| Format | Extension |
|--------|-----------|
| JPEG   | `.jpg`, `.jpeg` |
| PNG    | `.png` |
| WebP   | `.webp` |
| PDF    | `.pdf` |

---

## Development Setup (Linux)

### Prerequisites

- Python 3.10 or later
- Git

### Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd anything_to_pdf

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
PYTHONPATH=src python main.py
```

### Running Tests

```bash
source .venv/bin/activate
PYTHONPATH=src pytest tests/ -v
```

---

## Project Structure

```
anything_to_pdf/
├── main.py                    # Entry point
├── requirements.txt           # Runtime dependencies
├── requirements-dev.txt       # Development dependencies
├── src/
│   └── anything_to_pdf/
│       ├── __init__.py
│       ├── app.py             # QApplication setup
│       ├── main_window.py     # Main window
│       ├── arrange_area.py    # Horizontal file arrangement widget
│       ├── file_card.py       # Individual file card widget
│       ├── pdf_engine.py      # PDF generation (in-memory)
│       ├── thumbnails.py      # Thumbnail generation
│       ├── counter.py         # Sequential filename counter
│       └── worker.py          # Background PDF generation thread
├── tests/
│   ├── conftest.py            # Shared fixtures
│   ├── test_counter.py        # Counter tests
│   ├── test_pdf_engine.py     # PDF generation tests
│   └── test_ordering.py      # Ordering / widget tests
├── assets/                    # Icons and resources
└── packaging/
    ├── anything_to_pdf.spec   # PyInstaller spec (Windows)
    └── build_windows.bat      # Windows build script
```

---

## Windows Packaging (on a Windows Machine)

> ⚠️ The Windows executable **must be built on Windows**. Cross-compilation from Linux is not supported by PyInstaller.

### Steps

1. Install **Python 3.11+** from [python.org](https://python.org) (add to PATH during install).
2. Copy the project to your Windows machine (or clone via Git).
3. Open **Command Prompt** in the project root.
4. Run:

```bat
packaging\build_windows.bat
```

This will:
- Create a virtual environment
- Install all dependencies
- Run the full test suite
- Build `dist\AnythingToPDF.exe` using PyInstaller

5. Test `dist\AnythingToPDF.exe` on Windows 11.

### Notes

- The executable is a **single file** (no installer needed).
- Settings are stored in `%APPDATA%\AnythingToPDF\settings.json`.
- No installation or admin rights required to run the executable.

---

## Privacy & Security

- **100% offline** — no network calls ever made.
- **No telemetry** — no usage data is collected.
- **No accounts** — no sign-in required.
- All document processing happens locally on your machine.
- Only the final combined PDF is written to disk.

---

## Known Limitations

- Password-protected PDFs cannot be combined (must remove password first).
- Very large image files (>4096px on any side) are automatically downscaled to 4096px.
- Windows executable must be built on a Windows machine.
- WebP animated images use only the first frame.
- EXIF orientation is applied automatically, but malformed EXIF data may be ignored.
