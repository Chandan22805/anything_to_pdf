"""
Tests for the FilenameCounter class.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from anything_to_pdf.counter import COUNTER_MAX, COUNTER_MIN, FilenameCounter


# ---------------------------------------------------------------------------
# Counter basics
# ---------------------------------------------------------------------------


def test_initial_counter_starts_at_1(tmp_path):
    counter = FilenameCounter(tmp_path / "settings.json")
    assert counter.current == 1
    assert counter.peek() == "combined1.pdf"


def test_peek_does_not_advance(tmp_path):
    counter = FilenameCounter(tmp_path / "settings.json")
    assert counter.peek() == "combined1.pdf"
    assert counter.peek() == "combined1.pdf"
    assert counter.current == 1


def test_advance_returns_used_filename_and_increments(tmp_path):
    counter = FilenameCounter(tmp_path / "settings.json")
    name = counter.advance()
    assert name == "combined1.pdf"
    assert counter.current == 2
    assert counter.peek() == "combined2.pdf"


def test_sequential_increments(tmp_path):
    counter = FilenameCounter(tmp_path / "settings.json")
    names = [counter.advance() for _ in range(5)]
    assert names == [
        "combined1.pdf",
        "combined2.pdf",
        "combined3.pdf",
        "combined4.pdf",
        "combined5.pdf",
    ]
    assert counter.current == 6


def test_reset_after_9999(tmp_path):
    settings = tmp_path / "settings.json"
    counter = FilenameCounter(settings)
    # Wind counter up to 9999
    import json
    settings.write_text(json.dumps({"counter": COUNTER_MAX}))
    counter = FilenameCounter(settings)
    assert counter.peek() == "combined9999.pdf"
    name = counter.advance()
    assert name == "combined9999.pdf"
    # Should wrap back to 1
    assert counter.current == COUNTER_MIN
    assert counter.peek() == "combined1.pdf"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_persistence_across_restarts(tmp_path):
    settings = tmp_path / "settings.json"
    c1 = FilenameCounter(settings)
    c1.advance()   # → 1 used, now at 2
    c1.advance()   # → 2 used, now at 3

    # Simulate restart
    c2 = FilenameCounter(settings)
    assert c2.current == 3
    assert c2.peek() == "combined3.pdf"


def test_corrupted_settings_falls_back_to_1(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("not valid json!!!")
    counter = FilenameCounter(settings)
    assert counter.current == 1


def test_missing_settings_file(tmp_path):
    counter = FilenameCounter(tmp_path / "nonexistent" / "settings.json")
    assert counter.current == 1


def test_out_of_range_value_in_settings_falls_back_to_1(tmp_path):
    settings = tmp_path / "settings.json"
    import json
    settings.write_text(json.dumps({"counter": 99999}))
    counter = FilenameCounter(settings)
    assert counter.current == 1


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


def test_manual_reset(tmp_path):
    settings = tmp_path / "settings.json"
    counter = FilenameCounter(settings)
    counter.advance()
    counter.advance()
    counter.reset()
    assert counter.current == 1
    assert counter.peek() == "combined1.pdf"
