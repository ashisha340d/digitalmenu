# Digital Menu — Tray Launcher

A Windows system-tray application that replaces `START-MENU.bat` (kept as
`START-MENU.bat.legacy` for reference, no longer used). It starts
`menu_server.py`, keeps it running, and exposes the Digital Menu on your LAN —
all with no visible console window.

## Folder structure

```
MENU/
  TrayLauncher.pyw        entry point — double-click this, no console window
  run_debug.py            same app, but with a visible console (troubleshooting)
  build_exe.bat            builds DigitalMenuLauncher.exe via PyInstaller
  config.json               launcher settings (host/port/auto-restart/...)
  requirements.txt
  menu_server.py            existing backend (small patch: configurable host/port, graceful shutdown)
  Menu.xlsx, admin.html, digital-menu.html, images/, ...   unchanged
  logs/
    launcher.log            launcher lifecycle events
    server.log               menu_server.py's stdout/stderr, timestamped
  launcher/                  launcher source (clean modules, no globals)
    config.py                 loads/validates config.json
    logger.py                  sets up the two log files
    network_utils.py            LAN IP detection, port checks, URL building
    preflight.py                 Python / Menu.xlsx / openpyxl checks
    process_manager.py           spawns, monitors, restarts, stops menu_server.py
    browser_utils.py             waits for the server, opens the browser once
    notifications.py             tray toasts + blocking error dialogs
    icon_assets.py                draws the tray icon (no .ico file needed)
    tray_manager.py               tray menu, tooltip, double-click
    app.py                        wires all of the above together
```

## Dependencies

```
pystray>=0.19.5
Pillow>=10.0
openpyxl>=3.1
```

Install with:

```
python -m pip install -r requirements.txt
```

(`openpyxl` is also auto-installed at launch if missing — see Startup checks below.)

## Run instructions

**Normal use:** double-click `TrayLauncher.pyw`. Windows runs `.pyw` files with
`pythonw.exe`, which has no console window, by default. A tray icon appears;
the admin page and digital menu open automatically the first time the server
responds.

**Troubleshooting:** run `python run_debug.py` from a terminal — identical
app, but logs also print to that console.

**As a standalone .exe:** run `build_exe.bat` once (requires Python + pip).
It produces `DigitalMenuLauncher.exe` in this folder via PyInstaller
(`--onefile --noconsole`). Double-click that instead of `TrayLauncher.pyw`.
The .exe still needs a system Python on PATH at runtime, because it only
launches `menu_server.py` — it does not bundle a Python interpreter for it.

**Auto-start with Windows (optional):** put a shortcut to `TrayLauncher.pyw`
(or `DigitalMenuLauncher.exe`) in
`shell:startup` (Win+R → `shell:startup`).

## What happens on launch

1. Checks Python is available (for the frozen `.exe`, looks for `python`/`pythonw` on PATH).
2. Checks `Menu.xlsx` exists.
3. Checks `openpyxl` is importable; installs it automatically if not.
4. Starts `menu_server.py` as a hidden child process, bound to `config.json`'s
   `host`/`port` (default `0.0.0.0:8080`, so it's reachable on the LAN).
5. Polls `http://localhost:<port>/admin.html` until it responds.
6. Opens the admin page and the digital menu in the default browser — once.
7. Shows a tray icon; right-click for the menu, double-click opens the digital menu.

If port `8080` is already serving something when the launcher starts (e.g. a
previous instance), it reuses it instead of failing, and shows a
"Port Already In Use" notification.

## Tray menu

`Open Admin` · `Open Digital Menu` · `Open Menu Folder` · `Copy Network URL` ·
`Open Network URL` · `Restart Server` · `View Logs` · `About` · `Exit`

The tooltip shows `Running` / `Stopped` / `Starting...` / `Error` plus the LAN
IP and port. The tray icon's status dot reflects the same state.

## Server monitoring & restart

The launcher watches the `menu_server.py` process continuously. If it exits
unexpectedly, the launcher restarts it automatically — up to
`maxRestartAttempts` (default 3) — with a "Server Restarted" notification each
time. After the limit is hit, it stops trying and shows an error notification
instead of looping forever.

## Shutdown

`Exit` in the tray menu stops `menu_server.py` gracefully: it POSTs to the
server's loopback-only `/api/shutdown` endpoint, which the server catches to
close its socket cleanly, force-killing the process after a 5-second timeout
if it doesn't respond, then removes the tray icon and exits.

As a last-resort safety net, `menu_server.py` also runs inside a Windows Job
Object — if the launcher itself is ever killed abruptly (crash, Task Manager
"End Task") without a chance to run its own shutdown logic, Windows tears
down the server process automatically instead of leaving it orphaned on the
port.

## Configuration — `config.json`

```json
{
  "host": "0.0.0.0",
  "port": 8080,
  "autoOpenBrowser": true,
  "autoRestart": true,
  "maxRestartAttempts": 3
}
```

Missing or invalid fields fall back to these defaults automatically; the file
is rewritten with the effective, validated values on every launch.

## Logs

`logs/launcher.log` — startup checks, process lifecycle, restarts, errors.
`logs/server.log` — everything `menu_server.py` prints, with timestamps.
Both are plain text; open via the tray menu's `View Logs` (opens the folder).

## Error handling

| Situation | Behavior |
|---|---|
| Python missing | Blocking dialog before the tray icon ever appears |
| `Menu.xlsx` missing | Blocking dialog, launcher exits |
| `openpyxl` missing | Installed automatically via pip; blocking dialog only if that install fails |
| Port already in use | Reuses the existing server; "Port Already In Use" notification |
| Server crash | Auto-restarts up to `maxRestartAttempts`, then notifies and stops trying |
| Firewall prompt | Windows may prompt to allow `python.exe`/`DigitalMenuLauncher.exe` through the firewall the first time it binds `0.0.0.0:8080` — allow it (at least on Private networks) so other devices on the LAN can connect |
| Any other exception | Caught, logged to `logs/launcher.log`, surfaced as a notification or dialog — never a silent crash |

## Notes on the `menu_server.py` change

Three small, backend-only edits (frontend untouched):

- `host`/`port` are now read from the `MENU_SERVER_HOST` / `MENU_SERVER_PORT`
  environment variables (still defaulting to `0.0.0.0:8080` if unset), so the
  launcher can honor `config.json`.
- A loopback-only `POST /api/shutdown` endpoint sets an internal event that
  the main thread is waiting on, which then closes the listening socket
  cleanly and prints `Server stopped.` `serve_forever()` now runs on a
  background thread for this to work without deadlocking.
- Ctrl+C still works too if you ever run `python menu_server.py` directly in
  a visible terminal.
