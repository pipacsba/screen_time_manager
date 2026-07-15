# model.py
"""
Shared in-memory state for the current desktop session.

Multiple worker threads (WebSocket listener, REST synchronizer and
countdown) all exchange information through this object. Access is
protected by a lock to ensure updates remain consistent.
"""

import threading
from datetime import datetime, timezone

#
# Safe initial value used until the first state is received from
# Home Assistant. This prevents the countdown from immediately showing
# negative values while the initial synchronization is still in progress.
#
BOOTSTRAP_REMAINING = 600      # seconds


class ComputerTime:

    def __init__(self):

        #
        # Synchronizes access to the shared state.
        #
        self.lock = threading.Lock()

        #
        # True until the first successful synchronization with Home
        # Assistant. Workers may use this to distinguish bootstrap
        # values from real data.
        #
        self.bootstrap = True

        #
        # Latest computer-time state known locally.
        #
        # `remaining_base` is the remaining time reported by Home
        # Assistant at the moment `started` was recorded.
        #
        # The countdown thread continuously derives the live remaining
        # time from these values instead of requiring Home Assistant to
        # update every second.
        #
        self.active = True
        self.started = datetime.now(timezone.utc)
        self.remaining_base = BOOTSTRAP_REMAINING

        #
        # Current calculated remaining time.
        #
        # This field is currently unused and could be removed unless you
        # plan to cache the computed value here in the future.
        #
        self.remaining = BOOTSTRAP_REMAINING
