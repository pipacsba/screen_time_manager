# countdown.py
#
# Local countdown loop.
#
# This thread is responsible only for the local user experience:
#   • calculating the live remaining time
#   • writing status.json for the tray icon
#   • showing the "time is up" notification
#   • locking the session after the grace period
#
# Home Assistant remains the authoritative source of truth.
# Whenever HA publishes new values, they overwrite the local optimistic state.

from datetime import datetime, timezone
from dateutil.tz import tzlocal

import subprocess
import logging

logger = logging.getLogger(__name__)


def notify(title, message):
    """
    Show a desktop notification.

    Failures are intentionally ignored because notifications are
    non-critical and should never terminate the countdown thread.
    """
    subprocess.run(
        [
            "notify-send",
            title,
            message,
        ],
        check=False,
    )


def lock_screen():
    """
    Lock the current desktop session.

    The session manager will determine which graphical session to lock.
    """
    subprocess.run(
        [
            "loginctl",
            "lock-session",
        ],
        check=False,
    )


def format_time(seconds):
    """
    Format seconds as MM:SS or H:MM:SS.

    Negative values are handled by the caller.
    """

    if seconds is None:
        return "--:--"

    seconds = max(0, int(seconds))

    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"

    return f"{minutes}:{seconds:02}"


def countdown(model, status, stop_event):
    """
    Update the tray status once per second.

    The countdown is derived locally from the last state received from
    Home Assistant, allowing smooth second-by-second updates without
    polling HA every second.

    When time expires:

      1. notify the user
      2. start a one-minute grace period
      3. lock the session after the grace period

    During the grace period the model is updated optimistically.
    Home Assistant will shortly replace these values with the
    authoritative state.
    """

    last_text = None
    notification_sent = False

    while not stop_event.is_set():

        #
        # Read a consistent snapshot of the current model.
        #
        with model.lock:
            active = model.active
            started = model.started
            remaining_base = model.remaining_base

        #
        # Calculate the currently remaining time.
        #
        if active:

            try:
                elapsed = (
                    datetime.now(timezone.utc) - started
                ).total_seconds()

            except TypeError:
                #
                # Handle timestamps that unexpectedly lost timezone
                # information. This should be rare but avoids crashing
                # the countdown thread.
                #
                logger.error(
                    "Datetime mismatch: started=%r (tz=%r), now=%r (tz=%r)",
                    started,
                    started.tzinfo,
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc).tzinfo,
                )

                started = started.replace(tzinfo=tzlocal())
                elapsed = (
                    datetime.now(timezone.utc) - started
                ).total_seconds()

            remaining = remaining_base - elapsed

        else:
            #
            # Timer is paused (educational mode).
            #
            remaining = remaining_base

        #
        # Handle grace period.
        #
        if remaining >= 0:

            notification_sent = False

        else:

            #
            # Grace period has expired.
            #
            if notification_sent and remaining <= -60:

                lock_screen()

                #
                # Optimistically update the local model until Home
                # Assistant sends the real state.
                #
                with model.lock:
                    model.started = datetime.now(timezone.utc)
                    model.remaining_base = 0
                    model.active = False

                notification_sent = False

            #
            # Enter grace period.
            #
            elif not notification_sent:

                notify(
                    "Time is up",
                    "1 minute grace period started.",
                )

                notification_sent = True

                #
                # Restart the local timer so the tray displays the
                # elapsed grace period.
                #
                with model.lock:
                    model.started = datetime.now(timezone.utc)
                    model.remaining_base = 0
                    model.active = True

        display_remaining = remaining

        #
        # Select tray icon, text and colour.
        #
        if active:

            if display_remaining >= 0:

                text = f"🎮 {format_time(display_remaining)}"
                color = "green"
                tooltip = "Computer time remaining"

            else:

                text = f"⏳ -{format_time(-display_remaining)}"
                color = "red"
                tooltip = "Grace period - wrap up"

        else:

            text = f"📚 {format_time(display_remaining)}"
            color = "blue"
            tooltip = "Computer time paused"

        #
        # Only rewrite status.json when something visible changed.
        #
        if text != last_text:

            status.set(
                text=text,
                tooltip=tooltip,
                color=color,
            )

            last_text = text

        #
        # Sleep for up to one second, but wake immediately if the
        # application is shutting down.
        #
        if stop_event.wait(1):
            break
