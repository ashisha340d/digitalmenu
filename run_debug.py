"""Debug entry point — same app as TrayLauncher.pyw, but run with `python` so a
console window stays open and log output is mirrored to it. Use this when
troubleshooting a startup problem before switching back to TrayLauncher.pyw.
"""
import os
import sys

os.environ["LAUNCHER_CONSOLE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from launcher.app import run

if __name__ == "__main__":
    run()
