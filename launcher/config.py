"""Loads and validates config.json, filling in defaults for anything missing."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict

DEFAULTS = {
    "host": "0.0.0.0",
    "port": 8080,
    "autoOpenBrowser": True,
    "autoRestart": True,
    "maxRestartAttempts": 3,
}


@dataclass
class Config:
    host: str = DEFAULTS["host"]
    port: int = DEFAULTS["port"]
    autoOpenBrowser: bool = DEFAULTS["autoOpenBrowser"]
    autoRestart: bool = DEFAULTS["autoRestart"]
    maxRestartAttempts: int = DEFAULTS["maxRestartAttempts"]

    def to_dict(self) -> dict:
        return asdict(self)


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
