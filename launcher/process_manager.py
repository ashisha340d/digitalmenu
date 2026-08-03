"""Owns the menu_server.py subprocess: spawning, graceful/forced stop, and crash monitoring."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from .job_object import JobObject
from .network_utils import is_port_open


class ServerState:
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class ProcessManager:
    """Starts/stops menu_server.py and auto-restarts it (up to a limit) if it crashes.

    Not thread-safe across arbitrary callers beyond the locking already applied to the
    handful of public methods (start/stop/restart) — those are all that the tray UI
    and the internal monitor thread need to call.
    """

    def __init__(
        self,
        root: str,
        config,
        launcher_logger,
        server_logger,
        on_state_change=None,
        on_event=None,
        python_executable: str | None = None,
    ):
        self.root = root
        self.config = config
        self.log = launcher_logger
        self.server_log = server_logger
        self.on_state_change = on_state_change or (lambda state: None)
        self.on_event = on_event or (lambda name, **kwargs: None)
        self.python_exe = python_executable or sys.executable

        self._process: subprocess.Popen | None = None
        self._lock = threading.RLock()
        self._state = ServerState.STOPPED
        self._restart_count = 0
        self._stopping = False
        self._external_server = False
        self._monitor_thread: threading.Thread | None = None
        # Guarantees the child dies with us even on a hard kill (Task Manager, crash).
        self._job = JobObject(launcher_logger)

    @property
    def state(self) -> str:
        return self._state

    def is_running(self) -> bool:
        """Reflects actual process liveness, independent of when `mark_running()` was called."""
        if self._external_server:
            return self._state == ServerState.RUNNING
        return self._process is not None and self._process.poll() is None

    def mark_running(self) -> None:
        """Called once the caller has confirmed (e.g. via HTTP poll) that the server
        is actually answering requests — flips tray state from "starting" to "running"."""
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                self._set_state(ServerState.RUNNING)

    def _set_state(self, state: str) -> None:
        self._state = state
        try:
            self.on_state_change(state)
        except Exception:
            self.log.exception("state-change callback raised")

    def start(self) -> None:
        """Starts the server if it isn't already running (ours or an external one)."""
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                self.log.info("start() called but a server process is already running")
                return

            self._stopping = False
            host, port = self.config.host, self.config.port

            if is_port_open(host, port):
                self.log.warning(
                    "port %s already occupied before start — assuming an existing server instance", port
                )
                self._external_server = True
                self._set_state(ServerState.RUNNING)
                self.on_event("port_in_use_external")
                return

            self._external_server = False
            self._set_state(ServerState.STARTING)
            try:
                self._spawn()
            except Exception as exc:
                self.log.exception("failed to spawn menu_server.py")
                self._set_state(ServerState.ERROR)
                self.on_event("spawn_failed", error=str(exc))
                return

            if self._monitor_thread is None or not self._monitor_thread.is_alive():
                self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
                self._monitor_thread.start()

    def _spawn(self) -> None:
        env = dict(os.environ)
        env["MENU_SERVER_HOST"] = self.config.host
        env["MENU_SERVER_PORT"] = str(self.config.port)
        env["PYTHONUNBUFFERED"] = "1"
        script = os.path.join(self.root, "menu_server.py")

        self._process = subprocess.Popen(
            [self.python_exe, script],
            cwd=self.root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW,
            text=True,
            bufsize=1,
        )
        self.log.info(
            "spawned menu_server.py (pid=%s) on %s:%s", self._process.pid, self.config.host, self.config.port
        )
        self._job.assign(self._process)
        threading.Thread(target=self._pump_output, args=(self._process,), daemon=True).start()

    def _pump_output(self, proc: subprocess.Popen) -> None:
        try:
            for line in proc.stdout:
                self.server_log.info(line.rstrip())
        except Exception:
            pass

    def _monitor_loop(self) -> None:
        while True:
            proc = self._process
            if proc is None:
                return
            returncode = proc.wait()

            if self._stopping or self._external_server:
                self.log.info("server process exited (code=%s)", returncode)
                self._set_state(ServerState.STOPPED)
                self.on_event("server_stopped", code=returncode)
                return

            self.log.warning("server process exited unexpectedly (code=%s)", returncode)
            self._set_state(ServerState.ERROR)

            if not self.config.autoRestart:
                self.on_event("server_crashed_no_restart", code=returncode)
                return

            if self._restart_count >= self.config.maxRestartAttempts:
                self.log.error(
                    "max restart attempts (%s) reached — giving up", self.config.maxRestartAttempts
                )
                self.on_event("restart_limit_reached")
                return

            self._restart_count += 1
            attempt = self._restart_count
            time.sleep(1.5)

            with self._lock:
                if self._stopping:
                    return
                if is_port_open(self.config.host, self.config.port):
                    self.log.info("port reoccupied by another process during restart — treating as external")
                    self._external_server = True
                    self._set_state(ServerState.RUNNING)
                    self.on_event("port_in_use_external")
                    return
                try:
                    self._set_state(ServerState.STARTING)
                    self._spawn()
                except Exception:
                    self.log.exception("restart attempt %s failed", attempt)
                    self._set_state(ServerState.ERROR)
                    self.on_event("restart_failed")
                    return

            self.on_event("server_restarting", attempt=attempt, max_attempts=self.config.maxRestartAttempts)
            # Loop back around to wait on the newly spawned process.

    def _request_graceful_shutdown(self) -> bool:
        """Asks menu_server.py to stop via its loopback-only /api/shutdown endpoint.

        A console signal (CTRL_BREAK_EVENT) would be the more obvious approach, but it
        is not reliably delivered to a process launched with CREATE_NO_WINDOW — verified
        empirically, not just in theory — so shutdown is requested over HTTP instead,
        which works regardless of console/window state.
        """
        url = f"http://127.0.0.1:{self.config.port}/api/shutdown"
        try:
            urllib.request.urlopen(urllib.request.Request(url, data=b"{}", method="POST"), timeout=2)
            return True
        except urllib.error.URLError:
            return False

    def stop(self, timeout: float = 5.0) -> None:
        """Stops the server gracefully (HTTP shutdown request), force-killing after `timeout` seconds."""
        with self._lock:
            self._stopping = True
            proc = self._process
            if proc is None or proc.poll() is not None:
                self._set_state(ServerState.STOPPED)
                return

            self.log.info("stopping menu_server.py (pid=%s)", proc.pid)
            if not self._request_graceful_shutdown():
                self.log.warning("graceful shutdown request failed, will force-kill")

            try:
                proc.wait(timeout=timeout)
                self.log.info("server exited gracefully")
            except subprocess.TimeoutExpired:
                self.log.warning("graceful stop timed out after %ss — force killing", timeout)
                try:
                    proc.kill()
                    proc.wait(timeout=3)
                except Exception:
                    self.log.exception("force kill failed")

            self._set_state(ServerState.STOPPED)

    def restart(self) -> None:
        """Manual restart requested by the user — resets the crash-restart counter."""
        self.log.info("manual restart requested")
        self._restart_count = 0
        self.stop()
        time.sleep(0.5)
        self.start()
