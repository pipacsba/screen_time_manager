# countdown.py

import time
from datetime import datetime, timezone
from dateutil.tz import tzlocal

import subprocess
import logging

logger = logging.getLogger(__name__)

def notify(title, message):
    subprocess.run([
        "notify-send",
        title,
        message,
    ], check=False)


def lock_screen():
    subprocess.run([
        "loginctl",
        "lock-session",
    ], check=False)

def format_time(seconds):

    if seconds is None:
        return "--:--"

    seconds = max(0, int(seconds))

    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)

    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"

    return f"{minutes}:{seconds:02}"


def countdown(model, status, stop_event):

    last_text = None

    notification_sent = False

    while not stop_event.is_set():

        with model.lock:
            active = model.active
            started = model.started
            remaining_base = model.remaining_base

        if active:
            try:
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()

            except TypeError:
                logger.exception(
                   "Datetime mismatch: started=%r (tz=%r), now=%r (tz=%r)",
                    started,
                    started.tzinfo,
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc).tzinfo,
                )

                started = started.replace(tzinfo=tzlocal())
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
           
            remaining = remaining_base - elapsed
        
        else:
            remaining = remaining_base

        if remaining >= 0:
           notification_sent = False
        else:
            if notification_sent and remaining <= -60:
                lock_screen()
                # Local optimistic update.
                # Home Assistant will shortly overwrite these values with the authoritative state.
                with model.lock:
                     model.started = datetime.now(timezone.utc)
                     model.remaining_base = 0
                     model.active = False
                notification_sent = False
            elif not notification_sent:
                notify(
                    "Time is up",
                    "1 minute grace period started."
                )
                notification_sent = True
                with model.lock:
                     model.started = datetime.now(timezone.utc)
                     model.remaining_base = 0
                     model.active = True
                     
        display_remaining = remaining
                     
        if active:
            if display_remaining >=0:
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
            
        if text != last_text:
            status.set(
                text=text,
                tooltip=tooltip,
                color=color,
            )
            last_text = text

        stop_event.wait(1):
            break
