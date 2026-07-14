# homeassistant_ws.py

import json
import ssl
from datetime import datetime

import websocket
import logging

logger = logging.getLogger(__name__)

class HomeAssistantClient:

    def __init__(self, model, config, session, stop_event):
        self.model = model
        self.config = config
        self.session = session
        self.user = config.users[self.session.user]
        self.stop_event = stop_event

        self.ws = websocket.WebSocketApp(
            self.config.ha_url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )

    def run(self):
        self.ws.run_forever(
            sslopt={"cert_reqs": ssl.CERT_NONE}
        )

    def close(self):
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

        data = json.loads(message)
        #logger.debug("%s", data)
        msg_type = data.get("type")

        if msg_type == "auth_required":
            self._authenticate()
            return

        if msg_type == "auth_ok":
            self._subscribe()
            return

        if msg_type == "result":
            logger.info(json.dumps(data, indent=2))
            return

        if msg_type == "event":
            self._handle_event(data)
            return

    # ------------------------------------------------------------------
    # Home Assistant protocol
    # ------------------------------------------------------------------

    def _authenticate(self):

        logger.info("Authenticating...")

        self.ws.send(json.dumps({
            "type": "auth",
            "access_token": self.config.token,
        }))

    def _subscribe(self):

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

        trigger = data["event"]["variables"]["trigger"]

        entity = trigger["entity_id"]
        state = trigger["to_state"]["state"]

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

            self.model.bootstrap = False

        logger.info(
            "Synced: active=%s started=%s remaining=%s",
            self.model.active,
            self.model.started,
            self.model.remaining_base,
        )