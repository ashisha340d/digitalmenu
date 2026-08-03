"""Sets up file logging for the launcher itself and for the server subprocess's output."""
from __future__ import annotations

import logging
import os

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(root: str) -> tuple[logging.Logger, logging.Logger]:
    """Creates logs/launcher.log and logs/server.log, returns (launcher_logger, server_logger)."""
    logs_dir = os.path.join(root, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    launcher_logger = logging.getLogger("launcher")
    launcher_logger.setLevel(logging.DEBUG)
    launcher_logger.propagate = False
    if not launcher_logger.handlers:
        handler = logging.FileHandler(os.path.join(logs_dir, "launcher.log"), encoding="utf-8")
        handler.setFormatter(formatter)
        launcher_logger.addHandler(handler)

    server_logger = logging.getLogger("server")
    server_logger.setLevel(logging.DEBUG)
    server_logger.propagate = False
    if not server_logger.handlers:
        handler = logging.FileHandler(os.path.join(logs_dir, "server.log"), encoding="utf-8")
        handler.setFormatter(formatter)
        server_logger.addHandler(handler)

    # Debug entry point (run_debug.py) sets this so log output also shows up in the console.
    if os.environ.get("LAUNCHER_CONSOLE") == "1":
        for log in (launcher_logger, server_logger):
            if not any(isinstance(h, logging.StreamHandler) for h in log.handlers):
                console = logging.StreamHandler()
                console.setFormatter(formatter)
                log.addHandler(console)

    return launcher_logger, server_logger
