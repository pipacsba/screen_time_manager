# status.py
"""
Writes the current countdown state for consumption by desktop widgets.

The status is written as a JSON file inside the user's runtime directory.
Updates are performed atomically so readers never observe partially
written files.
"""

import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class StatusWriter:
    """
    Maintains the Waybar status file for a desktop session.

    The location is derived from the session's runtime directory so each
    logged-in user receives an independent status file.
    """    

    def __init__(self, session):
        """
        Prepare the runtime directory used to publish the status file.

        The directory is created on demand because the user's runtime
        directory is recreated on every login.
        
        Write to a temporary file first and then atomically replace the
        previous file. This guarantees that Waybar never reads a partially
        written JSON document.
        """
        
        self.session = session

        self.directory = session.runtime_dir / "ha-time"

        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.filename = self.directory / "status.json"

    def set(self, text, tooltip="", color="green"):
        """
        Update the published desktop status.

        Parameters
        ----------
        text
            Main text displayed by the desktop widget.
        tooltip
            Tooltip shown when hovering over the widget.
        color
            Semantic color name understood by the Waybar module.
        """

        status = {
            "version": 1,
            "text": text,
            "tooltip": tooltip,
            "color": color,
        }

        #
        # Atomic write.
        #
        tmp = self.filename.with_suffix(".tmp")

        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(
                status,
                f,
                ensure_ascii=False,
                indent=2,
            )

        tmp.replace(self.filename)
