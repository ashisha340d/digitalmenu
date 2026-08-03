"""Waits for the server to come up, then opens the admin/menu pages in the browser."""
from __future__ import annotations

import os
import subprocess
import time
import urllib.request
import webbrowser

# Chromium-family browsers accept --start-fullscreen, which is what makes the
# board fill the screen without anyone pressing F11 on the canteen PC.
CHROMIUM_CANDIDATES = [
    r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
    r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
    r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
    r"%LocalAppData%\Google\Chrome\Application\chrome.exe",
]


def wait_for_server(url: str, timeout: float = 30.0, interval: float = 0.4) -> bool:
    """Polls `url` until it responds (status < 500) or `timeout` seconds elapse."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def find_chromium() -> str | None:
    """Path to an installed Edge/Chrome, or None if neither is present."""
    for candidate in CHROMIUM_CANDIDATES:
        path = os.path.expandvars(candidate)
        if "%" not in path and os.path.exists(path):
            return path
    return None


def open_fullscreen(url: str) -> bool:
    """Opens `url` in its own full-screen browser window. False if unsupported."""
    browser = find_chromium()
    if not browser:
        return False
    try:
        subprocess.Popen([browser, "--new-window", "--start-fullscreen", url])
        return True
    except Exception:
        return False


def open_urls(urls: list[str]) -> None:
    """Opens each URL in a new browser tab, spaced slightly apart for reliability."""
    for url in urls:
        webbrowser.open_new_tab(url)
        time.sleep(0.3)
