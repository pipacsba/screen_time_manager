# model.py

import threading
from datetime import datetime, timezone
from enum import Enum

BOOTSTRAP_REMAINING = 600      # seconds

class ComputerTime:

    def __init__(self):

        self.lock = threading.Lock()

        #
        # True until the first update is received from Home Assistant.
        #
        self.bootstrap = True

        #
        # Current computer time state received from Home Assistant.
        #
        self.active = True
        self.started = datetime.now(timezone.utc)
        self.remaining_base = BOOTSTRAP_REMAINING
        self.remaining = BOOTSTRAP_REMAINING