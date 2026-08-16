"""Enumerates the attached monitors so each page can be opened on a chosen screen.

Windows-only, via user32 — deliberately no new dependency for something the OS
already answers. Everything here fails soft: if the display API is unavailable or
behaves unexpectedly, callers get an empty list and fall back to opening pages
without positioning them.

A note on coordinates: this module does *not* make the process DPI-aware. On a
scaled display an unaware process is told the monitor is 1280x720 rather than its
physical 1920x1080 — and that scaled figure is exactly the device-independent
pixel space Chromium's --window-position and --window-size expect. Becoming
DPI-aware here would report physical pixels and push windows off-screen.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", wintypes.DWORD),
    ]


_MONITORINFOF_PRIMARY = 0x1

_MONITOR_ENUM_PROC = ctypes.WINFUNCTYPE(
    ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(_RECT), wintypes.LPARAM
)


def list_monitors(logger=None) -> list[dict]:
    """Attached monitors, ordered so index 0 is the one a user would call "screen 1".

    Each entry is {index, x, y, w, h, work_w, work_h, primary}. The primary display
    sorts first, then the rest left-to-right and top-to-bottom — EnumDisplayMonitors'
    own order is not documented to match the numbering in Display Settings, so this
    imposes an order that at least matches how people describe their screens.
    """
    try:
        user32 = ctypes.windll.user32
    except (AttributeError, OSError):
        if logger:
            logger.info("no user32 available — screen placement disabled")
        return []

    found: list[dict] = []

    def _collect(hmonitor, _hdc, _lprect, _lparam):
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
            return 1
        mon, work = info.rcMonitor, info.rcWork
        found.append({
            "x": int(mon.left),
            "y": int(mon.top),
            "w": int(mon.right - mon.left),
            "h": int(mon.bottom - mon.top),
            "work_w": int(work.right - work.left),
            "work_h": int(work.bottom - work.top),
            "primary": bool(info.dwFlags & _MONITORINFOF_PRIMARY),
        })
        return 1

    try:
        if not user32.EnumDisplayMonitors(0, 0, _MONITOR_ENUM_PROC(_collect), 0):
            if logger:
                logger.warning("EnumDisplayMonitors reported failure")
    except Exception as exc:                                  # pragma: no cover
        if logger:
            logger.warning("could not enumerate monitors (%s) — screen placement disabled", exc)
        return []

    found.sort(key=lambda m: (not m["primary"], m["x"], m["y"]))
    for i, mon in enumerate(found):
        mon["index"] = i
    return found


def pick(monitors: list[dict], screen: int) -> dict | None:
    """The monitor for a 1-based `screen` number, or None if it isn't attached.

    Returning None is the signal to open the page without positioning it, which is
    what should happen when a two-screen board is booted on a one-screen machine.
    """
    if not monitors:
        return None
    try:
        n = int(screen)
    except (TypeError, ValueError):
        return None
    if n < 1 or n > len(monitors):
        return None
    return monitors[n - 1]


def describe(monitors: list[dict]) -> str:
    """One-line summary for the log, e.g. "1: 1920x1080 @0,0 (primary)"."""
    if not monitors:
        return "none detected"
    return "; ".join(
        f"{m['index'] + 1}: {m['w']}x{m['h']} @{m['x']},{m['y']}" + (" (primary)" if m["primary"] else "")
        for m in monitors
    )
