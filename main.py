#!/usr/bin/env python3
"""Entry point script for the application."""
import sys
import os

# Allow running from the repo root: python main.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from anything_to_pdf.app import main

if __name__ == "__main__":
    sys.exit(main())
