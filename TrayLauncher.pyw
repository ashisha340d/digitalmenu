"""Digital Menu tray launcher — primary entry point.

Double-click this file to start. It runs with no console window (via pythonw.exe,
which .pyw files are associated with by default on Windows). If double-click does
nothing, .pyw isn't associated with pythonw.exe on this machine — run instead:

    pythonw.exe TrayLauncher.pyw

or build DigitalMenuLauncher.exe with build_exe.bat and run that instead.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from launcher.app import run

if __name__ == "__main__":
    run()
