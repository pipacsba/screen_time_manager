# status.py

import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class StatusWriter:

    def __init__(self, session):

        self.session = session

        self.directory = session.runtime_dir / "ha-time"

        self.directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.filename = self.directory / "status.json"

    def set(self, text, tooltip="", color="green"):

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