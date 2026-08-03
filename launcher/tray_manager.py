"""Builds and runs the pystray tray icon: context menu, tooltip, and double-click behavior."""
from __future__ import annotations

import os
import subprocess
import webbrowser

import pystray

from . import notifications
from .icon_assets import build_icon

STATE_LABELS = {
    "running": "Running",
    "stopped": "Stopped",
    "starting": "Starting...",
    "error": "Error",
}


def build_icon_image(state: str):
    return build_icon(state)


def build_tooltip(state: str, port: int, lan_ip: str) -> str:
    label = STATE_LABELS.get(state, state.title())
    # Windows truncates tray tooltips at 127 characters.
    return f"Digital Menu — {label}\n{lan_ip}:{port}"[:127]


def _copy_to_clipboard(text: str) -> None:
    subprocess.run(
        ["clip"],
        input=text.encode("utf-16-le"),
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


class TrayManager:
    """Thin wrapper around a pystray.Icon — owns menu wiring, not server lifecycle."""

    def __init__(self, root: str, cfg, urls_provider, logs_dir: str, on_restart, on_exit):
        self.root = root
        self.cfg = cfg
        self.urls_provider = urls_provider
        self.logs_dir = logs_dir
        self.on_restart = on_restart
        self.on_exit = on_exit
        self.icon: pystray.Icon | None = None

    def _open_admin(self, icon=None, item=None):
        webbrowser.open_new_tab(self.urls_provider()["local_admin"])

    def _open_menu(self, icon=None, item=None):
        webbrowser.open_new_tab(self.urls_provider()["local_menu"])

    def _open_folder(self, icon=None, item=None):
        os.startfile(self.root)

    def _copy_network_url(self, icon=None, item=None):
        url = self.urls_provider()["lan_menu"]
        try:
            _copy_to_clipboard(url)
            if self.icon is not None:
                self.icon.notify(f"Copied: {url}", "Network URL Copied")
        except Exception:
            pass

    def _open_network_url(self, icon=None, item=None):
        webbrowser.open_new_tab(self.urls_provider()["lan_menu"])

    def _restart(self, icon=None, item=None):
        self.on_restart()

    def _view_logs(self, icon=None, item=None):
        os.startfile(self.logs_dir)

    def _about(self, icon=None, item=None):
        urls = self.urls_provider()
        notifications.show_info(
            "About Digital Menu",
            "Digital Menu Tray Launcher\n\n"
            f"Local:  {urls['local_menu']}\n"
            f"LAN:    {urls['lan_menu']}\n\n"
            "Right-click the tray icon for options.",
        )

    def _exit(self, icon, item=None):
        self.on_exit(icon)

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Open Admin", self._open_admin),
            pystray.MenuItem("Open Digital Menu", self._open_menu, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Menu Folder", self._open_folder),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Copy Network URL", self._copy_network_url),
            pystray.MenuItem("Open Network URL", self._open_network_url),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Restart Server", self._restart),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("View Logs", self._view_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("About", self._about),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self._exit),
        )

    def run(self, setup) -> None:
        """Blocks for the lifetime of the app (must be called on the main thread)."""
        self.icon = pystray.Icon(
            "digital_menu",
            icon=build_icon_image("starting"),
            title=build_tooltip("starting", self.cfg.port, "..."),
            menu=self._build_menu(),
        )
        self.icon.run(setup=setup)
