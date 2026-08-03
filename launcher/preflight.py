"""Startup checks: Python availability, Menu.xlsx presence, and the openpyxl dependency."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

WORKBOOK_CANDIDATES = ("Menu.xlsx", "Menu.xls", "menu.xlsx", "menu.xls")


class PreflightError(Exception):
    """Raised when a startup check fails in a way only the user can resolve."""


def resolve_python_executable() -> str:
    """Returns the python(w) executable to use for running menu_server.py.

    When this launcher itself is a frozen (PyInstaller) executable, sys.executable
    points at the launcher's own .exe rather than a real interpreter, so a system
    Python has to be located on PATH instead.
    """
    if getattr(sys, "frozen", False):
        exe = shutil.which("pythonw") or shutil.which("python")
        if not exe:
            raise PreflightError(
                "Python is not installed or not on PATH.\n\n"
                "Install Python from https://www.python.org/downloads/ and make sure "
                "\"Add Python to PATH\" is checked during setup, then try again."
            )
        return exe
    return sys.executable


def check_menu_workbook(root: str) -> str:
    """Confirms a menu workbook exists in `root`. Raises PreflightError if not."""
    for name in WORKBOOK_CANDIDATES:
        path = os.path.join(root, name)
        if os.path.exists(path):
            return path
    raise PreflightError(
        "Menu.xlsx was not found in:\n" + root + "\n\n"
        "Place your menu workbook there (named Menu.xlsx) and try again."
    )


def ensure_openpyxl(python_exe: str, logger) -> None:
    """Verifies openpyxl is importable under python_exe, installing it if missing."""
    probe = subprocess.run(
        [python_exe, "-c", "import openpyxl"],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if probe.returncode == 0:
        return

    logger.info("openpyxl not found under %s — installing automatically", python_exe)
    install = subprocess.run(
        [python_exe, "-m", "pip", "install", "--quiet", "openpyxl"],
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if install.returncode != 0:
        stderr_tail = install.stderr.decode("utf-8", "ignore")[-500:]
        raise PreflightError(
            "Failed to install the required 'openpyxl' package automatically.\n\n"
            "Try running this manually:\n"
            f'  "{python_exe}" -m pip install openpyxl\n\n{stderr_tail}'
        )
    logger.info("openpyxl installed successfully")
