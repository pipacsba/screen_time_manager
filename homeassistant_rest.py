# homeassistant_rest.py

import time
from datetime import datetime

import requests
import urllib3

import logging

logger = logging.getLogger(__name__)

# Allow self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HomeAssistantRestClient:

    def __init__(self, model, config, session, stop_event):

        self.model = model
        self.config = config
        self.session = session
        self.stop_event = stop_event

        self.user = config.users[session.user]

        self.base_url = config.ha_rest_url.rstrip("/")

        self.http = requests.Session()
        self.http.verify = False
        self.http.headers.update({
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
        })

    # --------------------------------------------------------------
    # Public
    # --------------------------------------------------------------

    def run(self):

        while not self.stop_event.is_set():


            try:
                self._refresh()

            except Exception:
                logger.exception("REST sync failed")

            if self.stop_event.wait(self.config.ha_poll_interval):
                break

    # --------------------------------------------------------------
    # Internal
    # --------------------------------------------------------------

    def _refresh(self):

        active = self._get_state(self.user.active_entity) == "on"

        started = datetime.fromisoformat(
            self._get_state(self.user.started_entity)
        )

        remaining = int(
            float(
                self._get_state(self.user.remaining_entity)
            )
        )

        with self.model.lock:
            self.model.active = active
            self.model.started = started
            self.model.remaining_base = remaining
            self.model.bootstrap = False

        logger.info(
            "REST sync: active=%s started=%s remaining=%s",
            active,
            started,
            remaining,
        )
        
    def _get_state(self, entity_id):

        response = self.http.get(
            f"{self.base_url}/states/{entity_id}",
            timeout=5,
        )

        response.raise_for_status()

        return response.json()["state"]



class HomeAssistantPublisher:

    def __init__(self, config):

        self.base_url = config.ha_rest_url.rstrip("/")
        self.ha_desktop_state_entity = config.ha_desktop_state_entity

        self.http = requests.Session()
        self.http.verify = False
        self.http.headers.update({
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
        })

    def publish_desktop_state(self, session):
        try:
            payload = {
                "state": "active" if session.interactive_session else "inactive",
                "attributes": {
                    "interactive_session": session.interactive_session,
                    "user": session.user,
                    "uid": session.uid,
                    "session": session.session,
                    "idle": session.idle,
                    "app": session.app,
                    "app_title": session.app_title,
                },
            }

            response = self.http.post(
                f"{self.base_url}/states/{self.ha_desktop_state_entity}",
                json=payload,
                timeout=5,
            )
            response.raise_for_status()

            logger.info(
                "Published desktop state for %s",
                session.user if session.interactive_session else "<none>",
            )

        except Exception:
            logger.exception("Failed to publish desktop state")