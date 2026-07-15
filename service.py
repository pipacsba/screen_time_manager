# service.py

from dataclasses import dataclass
from pathlib import Path
import subprocess
import json
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Session:
    interactive_session: bool
    user: Optional[str]
    uid: Optional[int]
    session: Optional[str]
    idle: bool
    runtime_dir: Optional[Path]
    bus: Optional[str]
    app: Optional[str]
    app_title: Optional[str]


def decode_gdbus_json(output: str) -> dict:
    output = output.strip()

    if not output.startswith("('") or not output.endswith("',)"):
        raise ValueError(f"Unexpected gdbus output: {output}")

    return json.loads(output[2:-3])


def focused_window(user: str, uid: int) -> dict:
    """
    Returns:
        {
            "app": "...",
            "title": "..."
        }
    """

    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"

    try:
        result = subprocess.run(
            [
                "runuser",
                "-u",
                user,
                "--",
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.Shell",
                "--object-path",
                "/org/gnome/shell/extensions/FocusedWindow",
                "--method",
                "org.gnome.shell.extensions.FocusedWindow.Get",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=3,
            check=True,
        )

        return decode_gdbus_json(result.stdout)

    except Exception:
        logger.exception("Failed to obtain focused window for %s", user)

        return {
            "app": "unknown",
            "title": "unknown",
        }


def get_active_session():
    """
    Returns the currently active desktop session.

    SSH sessions and other non-GNOME sessions are ignored.
    """

    result = subprocess.run(
        ["loginctl", "list-sessions", "--no-legend"],
        capture_output=True,
        text=True,
        check=True,
    )

    for line in result.stdout.splitlines():

        parts = line.split()

        #
        # Typical output:
        #
        # 2 1000 julcsi seat0
        # 5 1001 root   -
        #
        if len(parts) < 4:
            continue

        session_id = parts[0]
        user = parts[2]
        seat = parts[3]

        #
        # Ignore SSH / non-seat sessions.
        #
        if seat == "-":
            continue

        idle = subprocess.run(
            [
                "loginctl",
                "show-session",
                session_id,
                "-p",
                "IdleHint",
                "--value",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        if idle != "no":
            continue

        uid = int(
            subprocess.run(
                ["id", "-u", user],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )

        bus = Path(f"/run/user/{uid}/bus")

        #
        # A desktop session must have a session D-Bus.
        #
        if not bus.exists() or not bus.is_socket():
            continue

        return {
            "session": session_id,
            "user": user,
            "uid": uid,
            "idle": False,
        }

    return None


def discover_session() -> Session:

    session = get_active_session()

    if session is None:
        return Session(
            interactive_session=False,
            user=None,
            uid=None,
            session=None,
            idle=True,
            runtime_dir=None,
            bus=None,
            app=None,
            app_title=None,
        )

    window = focused_window(
        session["user"],
        session["uid"],
    )

    return Session(
        interactive_session=True,
        user=session["user"],
        uid=session["uid"],
        session=session["session"],
        idle=False,
        runtime_dir=Path(f"/run/user/{session['uid']}"),
        bus=f"unix:path=/run/user/{session['uid']}/bus",
        app=window.get("app"),
        app_title=window.get("title"),
    )
