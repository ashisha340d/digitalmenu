"""Windows notifications: tray balloon/toast messages plus blocking message boxes
for critical startup errors that occur before the tray icon exists.
"""
from __future__ import annotations

import ctypes

MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
MB_ICONINFORMATION = 0x00000040
MB_SYSTEMMODAL = 0x00001000


def show_blocking_error(title: str, message: str) -> None:
    """Modal error dialog — used for fatal startup problems the user must see and fix."""
    ctypes.windll.user32.MessageBoxW(0, message, title, MB_OK | MB_ICONERROR | MB_SYSTEMMODAL)


def show_info(title: str, message: str) -> None:
    """Modal info dialog — used for the "About" menu item."""
    ctypes.windll.user32.MessageBoxW(0, message, title, MB_OK | MB_ICONINFORMATION | MB_SYSTEMMODAL)


class Notifier:
    """Routes short status updates to the tray balloon/toast, and always to the log."""

    def __init__(self, logger):
        self._log = logger
        self._icon_provider = None

    def bind_icon_provider(self, provider) -> None:
        """`provider` is a zero-arg callable returning the current pystray Icon (or None)."""
        self._icon_provider = provider

    def notify(self, title: str, message: str) -> None:
        self._log.info("notify: %s — %s", title, message)
        icon = self._icon_provider() if self._icon_provider else None
        if icon is None:
            return
        try:
            icon.notify(message, title)
        except Exception:
            self._log.exception("tray notification failed")
