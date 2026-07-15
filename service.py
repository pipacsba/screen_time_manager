# service.py
"""
Discovers the currently active graphical desktop session.

This module identifies the user currently interacting with the local
desktop, ignoring SSH and other non-interactive sessions. It also
retrieves information about the focused application from a GNOME Shell
extension over the user's D-Bus session.
"""

from dataclasses import dataclass
from pathlib import Path
import subprocess
import json
import os
import logging
from typing import Optional
import pwd
import grp

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """
    Snapshot of the currently active desktop session.

    When no interactive desktop session exists, only
    `interactive_session` is False and all other fields are None.
    """    
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
    """
    Decode the output returned by

        gdbus call ...

    which has the form

        ('{ ...json... }',)

    and return the embedded JSON object.
    """    
    output = output.strip()

    if not output.startswith("('") or not output.endswith("',)"):
        raise ValueError(f"Unexpected gdbus output: {output}")

    return json.loads(output[2:-3])


def focused_window(user: str, uid: int) -> dict:
    """
    Query the GNOME Shell extension for the currently focused window.

    The command must execute inside the user's desktop session so the
    appropriate D-Bus environment variables are supplied.
    Returns:
        {
            "app": "...",
            "title": "..."
        }
    """

    env = os.environ.copy()
    env["XDG_RUNTIME_DIR"] = f"/run/user/{uid}"
    env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path=/run/user/{uid}/bus"

    pw = pwd.getpwnam(user)
    gid = pw.pw_gid
    
    try:
        result = subprocess.run(
            [
                "setpriv",
                f"--reuid={uid}",
                f"--regid={gid}",
                "--clear-groups",
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

    except subprocess.CalledProcessError as e:
        logger.error(
            "gdbus failed for %s:\nstdout=%s\nstderr=%s",
            user,
            e.stdout,
            e.stderr,
        )
    
        return {
            "wm_class": None,
            "title": None,
        }
    
    except Exception:
        logger.exception("Failed to obtain focused window for %s", user)
    
        return {
            "wm_class": None,
            "title": None,
        }

def get_active_session():
    """
    Locate the active local desktop session.

    Sessions are filtered to find the first one that

      - belongs to a physical seat,
      - is not idle, and
      - owns a session D-Bus socket.

    This excludes SSH and background sessions.
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
        uid = int(parts[1])
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

    #logger.info("Focused window: %r", window)

    return Session(
        interactive_session=True,
        user=session["user"],
        uid=session["uid"],
        session=session["session"],
        idle=False,
        runtime_dir=Path(f"/run/user/{session['uid']}"),
        bus=f"unix:path=/run/user/{session['uid']}/bus",
        app=window.get("wm_class"),
        app_title=window.get("title"),
    )
