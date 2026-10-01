#!/usr/bin/env python3
"""Narrow privileged Unix-socket service for Linuwu-Sense profile writes."""
import json
import os
import signal
import socket
import stat
import sys

SOCKET_DIR = "/run/linuwu-profile-helper"
SOCKET_PATH = SOCKET_DIR + "/profile.sock"
PROFILE_PATH = "/sys/devices/platform/acer-wmi/platform-profile/platform-profile-0/profile"
ALLOWED = frozenset(("low-power", "quiet", "balanced", "balanced-performance", "performance"))
MAX_REQUEST = 256


def reply(conn, ok, error=None):
    payload = {"ok": ok}
    if error:
        payload["error"] = error
    conn.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))


def handle(conn):
    conn.settimeout(2)
    data = bytearray()
    while len(data) <= MAX_REQUEST and b"\n" not in data:
        chunk = conn.recv(min(128, MAX_REQUEST + 1 - len(data)))
        if not chunk:
            break
        data.extend(chunk)
    if len(data) > MAX_REQUEST or b"\n" not in data or data.index(b"\n") != len(data) - 1:
        reply(conn, False, "Invalid request.")
        return
    try:
        request = json.loads(bytes(data).split(b"\n", 1)[0].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        reply(conn, False, "Invalid request.")
        return
    if (not isinstance(request, dict) or set(request) != {"action", "profile"}
            or request.get("action") != "set_profile"
            or not isinstance(request.get("profile"), str)
            or request["profile"] not in ALLOWED):
        reply(conn, False, "Unsupported action or profile.")
        return
    try:
        with open(PROFILE_PATH, "w", encoding="ascii") as profile:
            profile.write(request["profile"])
    except OSError:
        reply(conn, False, "Unable to update performance profile.")
        return
    reply(conn, True)


def main():
    os.makedirs(SOCKET_DIR, mode=0o750, exist_ok=True)
    group_gid = int(os.environ["LINUWU_GROUP_GID"])
    os.chown(SOCKET_DIR, 0, group_gid)
    os.chmod(SOCKET_DIR, 0o750)
    try:
        os.unlink(SOCKET_PATH)
    except FileNotFoundError:
        pass
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(SOCKET_PATH)
    os.chown(SOCKET_PATH, 0, group_gid)
    os.chmod(SOCKET_PATH, 0o660)
    server.listen(16)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    try:
        while True:
            conn, _ = server.accept()
            with conn:
                try:
                    handle(conn)
                except (OSError, ValueError):
                    pass
    finally:
        server.close()
        try:
            os.unlink(SOCKET_PATH)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    if os.geteuid() != 0:
        raise SystemExit("must run as root")
    main()
