# service.py

from dataclasses import dataclass
import time
from datetime import datetime
import subprocess
import os
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class Session:

    interactive_session: bool
    user: str
    uid: int
    session: str
    idle: bool
    runtime_dir: Path
    bus: str
    app: str
    app_title: str

def decode_gdbus_json(output: str) -> dict:
    """
    Decode the output of

        gdbus call ...

    which looks like

        ('{ "user": "exampleuser", "uid": 1001, "session": "16", "app": "tuxmath", "title": "Tux, of Math Command", "idle": false }',)
    """

    output = output.strip()

    if not output.startswith("('") or not output.endswith("',)"):
        raise ValueError(f"Unexpected gdbus output: {output}")

    json_text = output[2:-3]

    return json.loads(json_text)

def focused_window(user):

    #env = os.environ.copy()

    #env["XDG_RUNTIME_DIR"] = self.runtime_dir

    #env["DBUS_SESSION_BUS_ADDRESS"] = self.bus_address

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
        check=True,
    )

    return decode_gdbus_json(result.stdout)

def get_active_session():

    result = subprocess.run(
        ["loginctl", "list-sessions", "--no-legend"],
        capture_output=True,
        text=True,
        check=True,
    )

    for line in result.stdout.splitlines():

        parts = line.split()

        if len(parts) < 3:
            continue

        session_id = parts[0]
        user = parts[2]

        idle = subprocess.run(
            ["loginctl", "show-session", session_id, "-p", "IdleHint", "--value"],
            capture_output=True,
            text=True,
        ).stdout.strip()

        if idle != "no":
            continue

        uid = int(subprocess.run(
            ["id", "-u", user],
            capture_output=True,
            text=True,
        ).stdout.strip())

        return {
            "session": session_id,
            "user": user,
            "uid": uid,
            "idle": False,
        }

    return None
    
    
def discover_session():
    session = get_active_session()
    if not session:
        state = Session(
                interactive_session= False,
                user= "",
                uid= None,
                session= None,
                idle= True,
                runtime_dir= None,
                bus= None,
                app= None,
                app_title= None,
            )
    else:
        window = focused_window(session["user"])
        state = Session(
                interactive_session= True,
                user= session["user"],
                uid= session["uid"],
                session= session["session"],
                idle= session["idle"],
                runtime_dir= Path(f"/run/user/{session['uid']}"),
                bus= f"unix:path=/run/user/{session['uid']}/bus",
                app= window["app"],
                app_title= window["title"],
            )
    return state