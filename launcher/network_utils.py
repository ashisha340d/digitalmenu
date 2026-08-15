"""LAN IP discovery, port availability checks, and URL construction."""
from __future__ import annotations

import socket


def get_lan_ip() -> str:
    """Best-effort LAN IP of this machine (the address other devices would use).

    Opens a UDP "connection" to a public address without sending any packets —
    the OS just picks the outbound interface, which reveals the local IP.
    Falls back to hostname resolution, then loopback, if that's unavailable
    (e.g. no network connection at all).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        pass
    finally:
        sock.close()

    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


def is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """True if something is already listening on host:port."""
    probe_host = "127.0.0.1" if host == "0.0.0.0" else host
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        return sock.connect_ex((probe_host, port)) == 0
    except OSError:
        return False
    finally:
        sock.close()


def build_urls(port: int, lan_ip: str) -> dict:
    """Returns the standard set of URLs the app exposes, local and LAN.

    Local URLs use 127.0.0.1 rather than "localhost" on purpose: Windows resolves
    "localhost" to the IPv6 ::1 first, but the server binds IPv4 only, so every
    new connection pays a fallback delay (measured at ~2s per request here) —
    long enough that item photos show up as empty frames on the board.
    """
    return {
        "local_admin": f"http://127.0.0.1:{port}/admin.html",
        "local_menu": f"http://127.0.0.1:{port}/",
        "lan_admin": f"http://{lan_ip}:{port}/admin.html",
        "lan_menu": f"http://{lan_ip}:{port}/",
        "lan_root": f"http://{lan_ip}:{port}",
    }
