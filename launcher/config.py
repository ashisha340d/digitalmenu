"""Loads and validates config.json, filling in defaults for anything missing."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict

# Which page goes on which monitor, and how its window opens. `screen` is 1-based
# and matches display_utils' ordering (primary first, then left-to-right). A screen
# that isn't attached is not an error: that page opens unpositioned instead.
DEFAULT_SCREENS = [
    {"screen": 1, "page": "index.html", "state": "fullscreen"},
    {"screen": 2, "page": "admin.html", "state": "normal"},
]

# "borderless" is the fallback for when "fullscreen" lands on the wrong monitor —
# see browser_utils.open_page for why the two are not equally dependable.
VALID_STATES = ("fullscreen", "borderless", "maximized", "normal")

DEFAULTS = {
    "host": "0.0.0.0",
    "port": 8080,
    "autoOpenBrowser": True,
    "autoRestart": True,
    "maxRestartAttempts": 3,
    "screens": DEFAULT_SCREENS,
    # Each window gets its own browser profile so its placement flags survive: a
    # launch that shares a profile with a running browser is handed to that process
    # and its window flags are dropped. Turn off to reuse the normal profile.
    "isolateProfiles": True,
}


@dataclass
class Config:
    host: str = DEFAULTS["host"]
    port: int = DEFAULTS["port"]
    autoOpenBrowser: bool = DEFAULTS["autoOpenBrowser"]
    autoRestart: bool = DEFAULTS["autoRestart"]
    maxRestartAttempts: int = DEFAULTS["maxRestartAttempts"]
    screens: list = None
    isolateProfiles: bool = DEFAULTS["isolateProfiles"]

    def __post_init__(self):
        if self.screens is None:
            self.screens = [dict(s) for s in DEFAULT_SCREENS]

    def to_dict(self) -> dict:
        return asdict(self)


def _coerce_screens(raw) -> list:
    """Validates the screen list, dropping entries that name no page.

    An explicitly empty list is honoured — that means "open nothing on startup",
    which is different from the key being absent.
    """
    if not isinstance(raw, list):
        return [dict(s) for s in DEFAULT_SCREENS]

    out = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            continue
        page = str(entry.get("page") or "").strip().lstrip("/")
        if not page:
            continue
        try:
            screen = max(1, int(entry.get("screen", i + 1)))
        except (TypeError, ValueError):
            screen = i + 1
        state = str(entry.get("state") or "fullscreen").strip().lower()
        if state not in VALID_STATES:
            state = "fullscreen"
        out.append({"screen": screen, "page": page, "state": state})
    return out


def _coerce(raw: dict) -> dict:
    merged = dict(DEFAULTS)
    if isinstance(raw, dict):
        merged.update({k: v for k, v in raw.items() if k in DEFAULTS})
    merged["host"] = str(merged.get("host") or DEFAULTS["host"])
    try:
        merged["port"] = int(merged["port"])
    except (TypeError, ValueError):
        merged["port"] = DEFAULTS["port"]
    merged["autoOpenBrowser"] = bool(merged.get("autoOpenBrowser", True))
    merged["autoRestart"] = bool(merged.get("autoRestart", True))
    try:
        merged["maxRestartAttempts"] = max(0, int(merged["maxRestartAttempts"]))
    except (TypeError, ValueError):
        merged["maxRestartAttempts"] = DEFAULTS["maxRestartAttempts"]
    merged["screens"] = _coerce_screens(raw.get("screens") if isinstance(raw, dict) else None)
    merged["isolateProfiles"] = bool(merged.get("isolateProfiles", True))
    return merged


def load_config(root: str, logger=None) -> Config:
    """Reads config.json from `root`. Missing or corrupt files are replaced with defaults."""
    path = os.path.join(root, "config.json")
    raw = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            if logger:
                logger.warning("config.json unreadable (%s) — falling back to defaults", exc)
            raw = {}
    else:
        if logger:
            logger.info("config.json not found — creating one with defaults")

    merged = _coerce(raw)
    cfg = Config(**merged)

    # Persist back so the file always reflects the effective, validated settings.
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(cfg.to_dict(), fh, indent=2)
    except OSError as exc:
        if logger:
            logger.warning("could not write config.json: %s", exc)

    return cfg
