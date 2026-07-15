"""
homeassistant_ws.py

Maintains a persistent WebSocket connection to Home Assistant.

The WebSocket connection is used exclusively for real-time updates of the
computer time entities. Whenever Home Assistant changes one of the monitored
entities, the local model is updated immediately.

If the connection is lost, the client automatically reconnects until the
application is stopped.
"""

import json
import ssl
from datetime import datetime

import websocket
import logging

logger = logging.getLogger(__name__)


class HomeAssistantClient:
    """
    Receives real-time computer time updates from Home Assistant.

    One instance exists per monitored desktop session.
    """

    def __init__(self, model, config, session, stop_event):
        self.model = model
        self.config = config
        self.session = session
        self.user = config.users[self.session.user]
        self.stop_event = stop_event

        #
        # Configure the websocket client. Actual connection is established
        # later by run().
        #
        self.ws = websocket.WebSocketApp(
            self.config.ha_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

    def run(self):
        """
        Keep the websocket connected until the application is stopped.

        If Home Assistant is restarted or the network connection drops,
        automatically reconnect after a short delay.
        """

        while not self.stop_event.is_set():

            logger.info("Starting Home Assistant WS connection...")

            self.ws.run_forever(
                sslopt={"cert_reqs": ssl.CERT_NONE}
            )

            #
            # run_forever() returns only after the connection closes.
            #
            if not self.stop_event.is_set():
                logger.warning(
                    "WS connection lost. Reconnecting in 5 seconds..."
                )
                self.stop_event.wait(5)

    def close(self):
        """Close the websocket connection."""
        self.ws.close()

    # ------------------------------------------------------------------
    # WebSocket callbacks
    # ------------------------------------------------------------------

    def on_open(self, ws):
        logger.info("Connected to Home Assistant")

    def on_error(self, ws, error):
        logger.info("WS ERROR: %r", error)

    def on_close(self, ws, code, msg):
        logger.info("WS CLOSED: %s %s", code, msg)

    def on_message(self, ws, message):
        """
        Dispatch incoming Home Assistant websocket messages.
        """

        data = json.loads(message)
        # logger.debug("%s", data)

        msg_type = data.get("type")

        if msg_type == "auth_required":
            self._authenticate()
            return

        if msg_type == "auth_ok":
            self._subscribe()
            return

        if msg_type == "result":
            #
            # Response to one of our commands (authentication,
            # subscription, etc.).
            #
            logger.info(json.dumps(data, indent=2))
            return

        if msg_type == "event":
            #
            # State change notification for one of our subscribed entities.
            #
            self._handle_event(data)
            return

    # ------------------------------------------------------------------
    # Home Assistant protocol
    # ------------------------------------------------------------------

    def _authenticate(self):
        """Authenticate using the long-lived access token."""

        logger.info("Authenticating...")

        self.ws.send(json.dumps({
            "type": "auth",
            "access_token": self.config.token,
        }))

    def _subscribe(self):
        """
        Subscribe only to the three entities required by this user.

        Using subscribe_trigger greatly reduces websocket traffic compared
        to subscribing to every state change.
        """

        logger.info("Authentication successful.")

        self.ws.send(json.dumps({
            "id": 1,
            "type": "subscribe_trigger",
            "trigger": {
                "platform": "state",
                "entity_id": [
                    self.user.active_entity,
                    self.user.started_entity,
                    self.user.remaining_entity,
                ],
            },
        }))

        logger.info("Subscribed.")

    # ------------------------------------------------------------------
    # State updates
    # ------------------------------------------------------------------

    def _handle_event(self, data):
        """
        Update the shared computer time model from a Home Assistant event.
        """

        trigger = data["event"]["variables"]["trigger"]

        entity = trigger["entity_id"]
        state = trigger["to_state"]["state"]

        #
        # Protect the shared model while updating it.
        #
        with self.model.lock:

            if entity == self.user.active_entity:

                self.model.active = (state == "on")

            elif entity == self.user.started_entity:

                self.model.started = datetime.fromisoformat(state)

            elif entity == self.user.remaining_entity:

                self.model.remaining_base = int(float(state))

            else:

                logger.warning("Unexpected entity: %s", entity)
                return

            #
            # After the first successful update, the countdown thread can
            # trust the values stored in the model.
            #
            self.model.bootstrap = False

        logger.info(
            "Synced: active=%s started=%s remaining=%s",
            self.model.active,
            self.model.started,
            self.model.remaining_base,
        )
