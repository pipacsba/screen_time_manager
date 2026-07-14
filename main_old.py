import threading
import time

from config import load_config
from model import ComputerTime
from homeassistant_ws import HomeAssistantClient
from homeassistant_rest import HomeAssistantRestClient
from countdown import countdown
from status import StatusWriter
from logger import logger


def main():

    #
    # Load config + auto-select current OS user
    #
    config = load_config()
    user = config.user

    logger.info("Starting ha-monitor for user: %s", config.username)

    #
    # Shared state model
    #
    model = ComputerTime()

    #
    # Status output writer (writes to XDG_RUNTIME_DIR)
    #
    status = StatusWriter()

    #
    # Home Assistant WebSocket client
    #
    ha_ws = HomeAssistantClient(
        model=model,
        config=config,
        user=user,
    )

    #
    # Home Assistant REST client
    #
    ha_rest = HomeAssistantRestClient(
        model=model,
        config=config,
        user=user,
    )

    #
    # Countdown loop
    #
    threading.Thread(
        target=countdown,
        args=(model, status),
        daemon=True,
        name="countdown",
    ).start()
        
    #
    # Home Assistant WebSocket
    #
    threading.Thread(
        target=ha_ws.run,
        daemon=True,
        name="ha-ws",
    ).start()
        
    #
    # Home Assistant REST polling
    #
    threading.Thread(
        target=ha_rest.run,
        daemon=True,
        name="ha-rest",
    ).start()
        
    #
    # Keep main thread alive
    #
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        ha_ws.close()
    
        
if __name__ == "__main__":
    main()