"""Orchestrates startup: config, logging, preflight checks, the server process, and the tray icon."""
from __future__ import annotations

import os
import threading

from . import display_utils, network_utils, notifications, tray_manager
from .browser_utils import open_fullscreen, open_page, open_urls, wait_for_server
from .config import load_config
from .logger import setup_logging
from .preflight import PreflightError, check_menu_workbook, ensure_openpyxl, resolve_python_executable
from .process_manager import ProcessManager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILE_ROOT = os.path.join(ROOT, ".browser-profiles")


def _profile_dir(cfg, index: int, page: str) -> str | None:
    """Per-window browser profile path, or None when profile isolation is off."""
    if not cfg.isolateProfiles:
        return None
    safe = "".join(ch if ch.isalnum() else "-" for ch in page).strip("-") or "page"
    path = os.path.join(PROFILE_ROOT, f"{index + 1}-{safe}")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return None
    return path


def open_configured_screens(cfg, log) -> None:
    """Opens each configured page on its screen, degrading rather than failing.

    The fallbacks, in order: a screen that isn't attached means that page opens
    unpositioned; no Chromium at all means every page opens as an ordinary tab in
    the default browser. Either way the board still comes up, which matters more on
    an unattended canteen PC than getting the arrangement right.
    """
    base = f"http://127.0.0.1:{cfg.port}/"
    screens = cfg.screens or []
    if not screens:
        log.info("no screens configured — nothing opened on startup")
        return

    monitors = display_utils.list_monitors(log)
    log.info("displays detected — %s", display_utils.describe(monitors))

    urls = [base + entry["page"] for entry in screens]

    if not monitors:
        log.info("no displays resolved — opening every page without positioning")

    opened_any = False
    for i, entry in enumerate(screens):
        monitor = display_utils.pick(monitors, entry["screen"])
        if monitor is None and monitors:
            log.info(
                "screen %s is not attached — opening %s without positioning it",
                entry["screen"], entry["page"],
            )
        if open_page(urls[i], monitor, entry["state"], _profile_dir(cfg, i, entry["page"]), log):
            opened_any = True
        else:
            log.info("no Chromium browser found — falling back to the default browser")
            open_urls(urls)
            return

    if not opened_any:
        open_urls(urls)


def run() -> None:
    launcher_log, server_log = setup_logging(ROOT)
    launcher_log.info("=" * 60)
    launcher_log.info("Digital Menu launcher starting (root=%s)", ROOT)

    try:
        cfg = load_config(ROOT, launcher_log)
    except Exception:
        launcher_log.exception("failed to load config")
        notifications.show_blocking_error(
            "Digital Menu — Startup Error",
            "Could not load config.json. Check logs\\launcher.log for details.",
        )
        return

    try:
        python_exe = resolve_python_executable()
    except PreflightError as exc:
        launcher_log.error("Python missing: %s", exc)
        notifications.show_blocking_error("Digital Menu — Python Missing", str(exc))
        return

    try:
        check_menu_workbook(ROOT)
    except PreflightError as exc:
        launcher_log.error("Menu.xlsx missing: %s", exc)
        notifications.show_blocking_error("Digital Menu — Menu.xlsx Missing", str(exc))
        return

    try:
        ensure_openpyxl(python_exe, launcher_log)
    except PreflightError as exc:
        launcher_log.error("openpyxl unavailable: %s", exc)
        notifications.show_blocking_error("Digital Menu — Missing Dependency", str(exc))
        return

    lan_ip = network_utils.get_lan_ip()
    launcher_log.info("LAN IP detected: %s", lan_ip)

    notifier = notifications.Notifier(launcher_log)
    browser_opened = threading.Event()

    def current_urls():
        return network_utils.build_urls(cfg.port, network_utils.get_lan_ip())

    def handle_state_change(state):
        icon = tray.icon
        if icon is None:
            return
        try:
            icon.icon = tray_manager.build_icon_image(state)
            icon.title = tray_manager.build_tooltip(state, cfg.port, lan_ip)
        except Exception:
            launcher_log.exception("failed to update tray icon for state=%s", state)

    def handle_event(name, **kwargs):
        if name == "port_in_use_external":
            notifier.notify(
                "Port Already In Use",
                f"Port {cfg.port} is already serving something — reusing the existing server.",
            )
        elif name == "server_restarting":
            notifier.notify(
                "Server Restarted",
                f"Attempt {kwargs.get('attempt')} of {kwargs.get('max_attempts')} after an unexpected exit.",
            )
        elif name == "restart_limit_reached":
            notifier.notify(
                "Digital Menu — Server Error",
                f"The server crashed and could not be restarted after {cfg.maxRestartAttempts} attempts. "
                "Check logs\\server.log.",
            )
        elif name == "server_crashed_no_restart":
            notifier.notify("Server Stopped", "The server stopped unexpectedly and auto-restart is disabled.")
        elif name == "server_stopped":
            notifier.notify("Server Stopped", "The Digital Menu server has stopped.")
        elif name == "spawn_failed":
            notifier.notify("Digital Menu — Startup Error", f"Could not start the server: {kwargs.get('error')}")
        elif name == "restart_failed":
            notifier.notify("Digital Menu — Restart Failed", "Could not restart the server. Check logs\\launcher.log.")

    manager = ProcessManager(
        ROOT,
        cfg,
        launcher_log,
        server_log,
        on_state_change=handle_state_change,
        on_event=handle_event,
        python_executable=python_exe,
    )

    def on_restart_clicked():
        notifier.notify("Restarting Server", "Restarting the Digital Menu server...")

        def do_restart():
            manager.restart()
            urls = current_urls()
            if wait_for_server(urls["local_admin"], timeout=20.0):
                manager.mark_running()
                notifier.notify("Server Restarted", "The Digital Menu server is back up.")
            elif manager.is_running():
                pass  # an external server took the port; already notified via events
            else:
                notifier.notify("Digital Menu — Restart Failed", "The server did not come back up in time.")

        threading.Thread(target=do_restart, daemon=True).start()

    def on_exit_clicked(icon):
        launcher_log.info("Exit requested from tray menu")
        manager.stop()
        icon.visible = False
        icon.stop()

    tray = tray_manager.TrayManager(
        root=ROOT,
        cfg=cfg,
        urls_provider=current_urls,
        logs_dir=os.path.join(ROOT, "logs"),
        on_restart=on_restart_clicked,
        on_exit=on_exit_clicked,
    )
    notifier.bind_icon_provider(lambda: tray.icon)

    def startup_sequence(icon):
        icon.visible = True
        notifier.notify("Digital Menu Started", "Starting the server...")
        manager.start()

        urls = current_urls()
        ready = wait_for_server(urls["local_admin"], timeout=30.0)

        if ready:
            launcher_log.info("server is ready")
            manager.mark_running()
            notifier.notify(
                "Server Running",
                f"Digital Menu is live on port {cfg.port}.\nLAN: {urls['lan_menu']}",
            )
            if cfg.autoOpenBrowser and not browser_opened.is_set():
                browser_opened.set()
                open_configured_screens(cfg, launcher_log)
        else:
            launcher_log.error("server did not become ready within timeout")
            notifier.notify(
                "Digital Menu — Startup Error", "The server did not respond in time. Check logs\\server.log."
            )

    try:
        tray.run(setup=startup_sequence)
    except Exception:
        launcher_log.exception("fatal error in tray icon loop")
        notifications.show_blocking_error(
            "Digital Menu — Fatal Error", "The tray application crashed. See logs\\launcher.log for details."
        )
    finally:
        manager.stop()
        launcher_log.info("Digital Menu launcher exited")
