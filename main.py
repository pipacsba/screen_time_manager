# main.py
"""
Main entry point for the screen time monitor.

The service continuously watches for the currently active graphical
desktop session. Whenever a monitored user logs in, it starts the
components responsible for synchronizing with Home Assistant and
updating the local desktop status.

The desktop session is treated as the application's lifecycle. Workers
exist only while a monitored user owns an interactive desktop session.
This allows the same system service to transparently follow user logins,
logouts and fast user switching.
"""

import threading
import time

from config import load_config
from model import ComputerTime
from service import discover_session, Session
from homeassistant_ws import HomeAssistantClient
from homeassistant_rest import HomeAssistantRestClient, HomeAssistantPublisher
from countdown import countdown
from status import StatusWriter
from logger import setup_logging
import logging
import signal

setup_logging()
logger = logging.getLogger(__name__)

#
# How often we check whether the active desktop session changed.
#
SESSION_POLL_INTERVAL = 2

#
# Maximum interval between desktop-state publications to Home Assistant.
#
# This acts as a heartbeat. If the service disappears without publishing
# an inactive state (for example because of a power failure), Home Assistant
# can detect that the last known state has become stale.
#
HARTBEAT_INTERVAL = 20


def stop_workers(workers):
    """
    Gracefully stop all background workers.

    The WebSocket thread blocks inside run_forever(), therefore simply
    setting the stop event is not enough. Closing the socket wakes the
    thread so it can terminate cleanly. Waiting briefly for every thread
    avoids leaving background work running while a new user session is
    starting.
    """

    if workers is None:
        return

    workers["stop"].set()
    workers["ws"].close()

    for t in workers["threads"]:
        t.join(timeout=2)

def publish_inactive_desktop_state(ha_publisher):
    """
    Tell Home Assistant that no interactive desktop session is active.

    This is important during service shutdown: otherwise Home Assistant
    may retain the last active session state and continue to calculate
    screen time even though the monitor is no longer running.

    The Python model uses None for all session-specific values. 
    The HomeAssistantPublisher converts these to the appropriate values 
    for the published HA entity.
    """

    session = Session(
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

    try:
        ha_publisher.publish_desktop_state(session)
        logger.info("Published inactive desktop state during shutdown")
    except Exception:
        logger.exception(
            "Failed to publish inactive desktop state during shutdown"
        )

def shutdown(workers, ha_publisher):
    """
    Gracefully shut down the monitor.

    Workers are stopped first, then Home Assistant is explicitly told
    that there is no active desktop session. The latter prevents HA from
    continuing to treat the last known desktop state as active.
    """

    logger.info("Stopping.")

    stop_workers(workers)

    publish_inactive_desktop_state(ha_publisher)


def main():

    # 
    # systemd normally terminates the service using SIGTERM. 
    # SIGINT is also handled so Ctrl+C behaves in the same way when 
    # running the program manually from a terminal. 
    #
    def handle_signal(signum, frame):
        raise SystemExit

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    config = load_config()

    logger.info("Starting ha-monitor system service")

    #
    # Track the currently running worker set.
    # At most one interactive desktop session is monitored at a time.
    #
    workers = None
    current_user = None

    #
    # Remember the last published session so Home Assistant is only
    # updated when something actually changes.
    #
    old_session = None

    #
    # Publishing desktop state is independent from the computer-time
    # functionality. Even unmonitored users or the absence of an active
    # desktop session are still reported to Home Assistant.
    #
    ha_publisher = HomeAssistantPublisher(config)

    #initialize heartbeat counter
    heartbeat_elapsed = 0

    try:

        while True:

            #
            # Discover the current interactive desktop session.
            #
            # This is the single source of truth describing who currently
            # owns the physical desktop. It automatically detects logins,
            # logouts, user switching and changes of the focused
            # application.
            #
            session = discover_session()

            #
            # Publish desktop state only when something changed. This
            # avoids unnecessary REST traffic while still allowing Home
            # Assistant automations to react immediately.
            # Session is a dataclass, so equality compares all of its 
            # fields, including the focused application and window title.
            #
            if (session != old_session) or (heartbeat_elapsed >= HARTBEAT_INTERVAL):
                try:
                    ha_publisher.publish_desktop_state(session)
                    #
                    # Only consider the heartbeat successful after Home
                    # Assistant accepted the publication.
                    #
                    heartbeat_elapsed = 0
                    old_session = session
                    
                except Exception:
                    # 
                    # Do not update old_session when publishing fails. 
                    # This means the same state will be retried during 
                    # the next polling cycle. 
                    #
                    logger.warning("Failed to publish desktop state")
            else:
                heartbeat_elapsed = heartbeat_elapsed + SESSION_POLL_INTERVAL

            
            #
            # Workers should only exist while a configured user owns an
            # interactive desktop session.
            #
            # If nobody is logged in, or if an unknown user is using the
            # machine, stop all background activity. The desktop state is
            # still published above, but computer-time management is
            # intentionally disabled.
            #
            if (
                not session.interactive_session
                or session.user not in config.users
            ):

                if workers is not None:

                    if not session.interactive_session:

                        logger.debug("No interactive desktop session.")

                    else:
                        logger.debug("Ignoring unconfigured user '%s'", session.user )

                    stop_workers(workers)
                    workers = None
                    current_user = None

                time.sleep(SESSION_POLL_INTERVAL)
                continue

            #
            # A different user is now controlling the desktop.
            #
            # Every user has independent Home Assistant entities,
            # configuration and Waybar status file, so the simplest and
            # safest approach is to completely rebuild the worker set for
            # the new session.
            #
            if session.user != current_user:

                if workers is not None:

                    logger.info("Stopping workers for %s", current_user )
                    stop_workers(workers)

                logger.info(
                    "Starting workers for %s",
                    session.user,
                )

                #
                # The shared model acts as the communication point
                # between the WebSocket listener, REST synchronizer and
                # countdown thread.
                #
                model = ComputerTime()

                #
                # StatusWriter is session-specific because each desktop
                # user has their own XDG runtime directory.
                #
                status = StatusWriter(session)

                #
                # One stop event is shared by every worker so they can be
                # terminated together.
                #
                stop_event = threading.Event()

                # 
                # Home Assistant WebSocket synchronization. 
                #
                ha_ws = HomeAssistantClient(
                    model=model,
                    config=config,
                    session=session,
                    stop_event=stop_event,
                )

                # 
                # Home Assistant REST synchronization. 
                #
                ha_rest = HomeAssistantRestClient(
                    model=model,
                    config=config,
                    session=session,
                    stop_event=stop_event,
                )

                #
                # The application separates responsibilities into three
                # independent workers:
                #
                #   • WebSocket: receives immediate updates from Home
                #     Assistant.
                #
                #   • REST: periodically refreshes the complete state so
                #     temporary WebSocket disconnects cannot leave the
                #     local model stale.
                #
                #   • Countdown: continuously derives the remaining time
                #     from the synchronized state and updates the local
                #     desktop status.
                #
                threads = [

                    threading.Thread(
                        target=countdown,
                        args=(model, status, session, stop_event),
                        daemon=True,
                        name="countdown",
                    ),

                    threading.Thread(
                        target=ha_ws.run,
                        daemon=True,
                        name="ha-ws",
                    ),

                    threading.Thread(
                        target=ha_rest.run,
                        daemon=True,
                        name="ha-rest",
                    ),
                ]

                for t in threads:
                    t.start()

                workers = {
                    "stop": stop_event,
                    "ws": ha_ws,
                    "threads": threads,
                }

                current_user = session.user

            #
            # Session discovery does not require sub-second precision.
            # Polling every few seconds keeps the implementation simple
            # while remaining responsive enough for logins and user
            # switches.
            #
            time.sleep(SESSION_POLL_INTERVAL)

    except (KeyboardInterrupt, SystemExit):
        shutdown(workers, ha_publisher)


if __name__ == "__main__":
    main()
