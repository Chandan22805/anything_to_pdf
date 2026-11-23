"""Persistent sequential filename counter for combined PDF output."""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

COUNTER_MIN = 1
COUNTER_MAX = 9999


def _settings_path() -> Path:
    """Return platform-appropriate path for the settings file."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    directory = base / "AnythingToPDF"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "settings.json"


class FilenameCounter:
    """Manages a persistent sequential counter for output filenames."""

    def __init__(self, settings_path: Path | None = None):
        self._path = settings_path or _settings_path()
        self._counter: int = self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current(self) -> int:
        return self._counter

    def peek(self) -> str:
        """Return the next filename without advancing the counter."""
        return f"combined{self._counter}.pdf"

    def advance(self) -> str:
        """Advance the counter and persist it. Return the filename that was used."""
        filename = self.peek()
        next_value = self._counter + 1
        if next_value > COUNTER_MAX:
            next_value = COUNTER_MIN
        self._counter = next_value
        self._save()
        logger.debug("Counter advanced to %d, used filename: %s", self._counter, filename)
        return filename

    def reset(self) -> None:
        """Reset counter to 1 (for testing)."""
        self._counter = COUNTER_MIN
        self._save()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> int:
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                value = int(data.get("counter", COUNTER_MIN))
                if COUNTER_MIN <= value <= COUNTER_MAX:
                    logger.debug("Loaded counter value: %d from %s", value, self._path)
                    return value
        except Exception as exc:
            logger.warning("Could not load counter from %s: %s", self._path, exc)
        return COUNTER_MIN

    def _save(self) -> None:
        try:
            self._path.write_text(
                json.dumps({"counter": self._counter}, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("Could not save counter to %s: %s", self._path, exc)
