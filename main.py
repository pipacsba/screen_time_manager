# main.py

import threading
import time

from config import load_config
from model import ComputerTime
from service import discover_session
from homeassistant_ws import HomeAssistantClient
from homeassistant_rest import HomeAssistantRestClient, HomeAssistantPublisher
from countdown import countdown
from status import StatusWriter
from logger import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)

def main():

    config = load_config()

    logger.info("Starting ha-monitor system service")

    workers = None
    current_user = None
    old_session = None
    ha_rest_push = HomeAssistantPublisher(config)

    try:

        while True:

            session = discover_session()
            
            if session != old_session:
                try:
                    ha_rest_push.publish_desktop_state(session)
                    old_session = session
                except Exception:
                    logger.exception("Failed to publish desktop state")

            #
            # No active desktop session
            #
            if not session.interactive_session:

                if workers is not None:

                    logger.info("Desktop session ended.")

                    workers["stop"].set()

                    workers["ws"].close()

                    workers = None
                    current_user = None

                time.sleep(2)
                continue

            #
            # User changed (or first login)
            #
            if session.user != current_user:

                if workers is not None:

                    logger.info("Stopping workers for %s", current_user)

                    workers["stop"].set()
                    workers["ws"].close()

                logger.info("Starting workers for %s", session.user)

                model = ComputerTime()
                status = StatusWriter(session)

                stop_event = threading.Event()

                ha_ws = HomeAssistantClient(
                    model=model,
                    config=config,
                    session=session,
                    stop_event=stop_event,
                )

                ha_rest = HomeAssistantRestClient(
                    model=model,
                    config=config,
                    session=session,
                    stop_event=stop_event,
                )

                threads = [

                    threading.Thread(
                        target=countdown,
                        args=(model, status, stop_event),
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

            time.sleep(2)

    except KeyboardInterrupt:

        logger.info("Stopping.")

        if workers is not None:
            workers["stop"].set()
            workers["ws"].close()


if __name__ == "__main__":
    main()
