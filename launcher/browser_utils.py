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


def open_page(url: str, monitor: dict | None = None, state: str = "fullscreen",
              profile_dir: str | None = None, logger=None) -> bool:
    """Opens `url` in its own window, on `monitor` if one was resolved.

    `state` is "fullscreen", "borderless", "maximized", or "normal". Returns False
    if no Chromium is installed, which is the caller's cue to fall back to the
    default browser.

    Two things here are load-bearing on a multi-screen setup:

    * `profile_dir` — a second launch that shares a profile with a running browser
      is forwarded to that existing process, which then ignores every window flag
      passed on the command line. Giving each window its own --user-data-dir keeps
      the placement flags meaningful, at the cost of a separate browser process.
    * `--window-position` is passed even for the fullscreen state, because it is
      what decides *which* display the window fullscreens onto.

    "borderless" exists because those two flags are not equally dependable:
    --window-position is honoured exactly, while --start-fullscreen has been known
    to fullscreen onto the launching window's display and ignore the position.
    Borderless asks for an --app window sized to the monitor's full bounds, which
    reaches the same chrome-less result using only the reliable mechanism. Use it
    if a fullscreen board comes up on the wrong screen.
    """
    browser = find_chromium()
    if not browser:
        return False

    args = [browser]
    if state == "borderless":
        args.append(f"--app={url}")
    else:
        args.append("--new-window")

    if profile_dir:
        args += [f"--user-data-dir={profile_dir}", "--no-first-run", "--no-default-browser-check"]

    if monitor:
        args.append(f"--window-position={monitor['x']},{monitor['y']}")
        if state in ("fullscreen", "borderless"):
            args.append(f"--window-size={monitor['w']},{monitor['h']}")
        else:
            # Leave room for the taskbar so a "normal" window isn't half under it.
            args.append(f"--window-size={monitor['work_w']},{monitor['work_h']}")

    if state == "fullscreen":
        args.append("--start-fullscreen")
    elif state == "maximized":
        args.append("--start-maximized")

    if state != "borderless":
        args.append(url)                               # --app already carries the URL

    try:
        subprocess.Popen(args)
        if logger:
            where = f"screen {monitor['index'] + 1}" if monitor else "wherever the browser puts it"
            logger.info("opened %s (%s) on %s", url, state, where)
        return True
    except Exception as exc:
        if logger:
            logger.warning("could not launch the browser for %s: %s", url, exc)
        return False


def open_urls(urls: list[str]) -> None:
    """Opens each URL in a new browser tab, spaced slightly apart for reliability."""
    for url in urls:
        webbrowser.open_new_tab(url)
        time.sleep(0.3)
