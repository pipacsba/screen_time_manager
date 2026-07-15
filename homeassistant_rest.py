# homeassistant_rest.py
#
# Home Assistant REST API client.
#
# This module contains two independent REST clients:
#
#   HomeAssistantRestClient
#       Periodically downloads the current computer-time state
#       (active, started timestamp, remaining seconds) from
#       Home Assistant into the shared model.
#
#   HomeAssistantPublisher
#       Publishes the currently active desktop session
#       (logged-in user, focused application, idle state, ...)
#       as a Home Assistant entity so automations can react
#       to desktop activity.
#

from datetime import datetime
import logging

import requests
import urllib3

logger = logging.getLogger(__name__)

#
# Home Assistant commonly uses self-signed certificates in
# private networks. Suppress the resulting HTTPS warnings.
#
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HomeAssistantRestClient:
    """
    Periodically synchronizes the computer-time model from
    Home Assistant using the REST API.

    This acts as a safety net in case WebSocket events are missed
    and also provides the initial bootstrap values after login.
    """

    def __init__(self, model, config, session, stop_event):

        self.model = model
        self.config = config
        self.session = session
        self.stop_event = stop_event

        #
        # Configuration for the currently logged-in user.
        #
        self.user = config.users[session.user]

        self.base_url = config.ha_rest_url.rstrip("/")

        #
        # Reuse one HTTP session for all requests.
        #
        self.http = requests.Session()
        self.http.verify = False
        self.http.headers.update({
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
        })

    # --------------------------------------------------------------
    # Main polling loop
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
    # Internal helpers
    # --------------------------------------------------------------

    def _refresh(self):
        """
        Download the latest computer-time state from Home Assistant
        and update the shared model.
        """

        active = self._get_state(self.user.active_entity) == "on"

        started = datetime.fromisoformat(
            self._get_state(self.user.started_entity)
        )
        if started.tzinfo is None:
            started = started.replace(tzinfo=tzlocal())

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
            "REST sync: active=%s started=%s (tz=%r) remaining=%s",
            active,
            started,
            started.tzinfo,
            remaining,
        )

    def _get_state(self, entity_id):
        """
        Read the state value of a single Home Assistant entity.
        """

        response = self.http.get(
            f"{self.base_url}/states/{entity_id}",
            timeout=5,
        )

        response.raise_for_status()

        return response.json()["state"]


class HomeAssistantPublisher:
    """
    Publishes the currently active desktop session to Home Assistant.

    Unlike HomeAssistantRestClient, this class does not run in its own
    thread. The main loop calls publish_desktop_state() whenever the
    detected desktop session changes.
    """

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
        """
        Publish the current desktop session as a Home Assistant entity.

        Empty strings are used instead of None so the entity always has
        stable attribute types.
        """

        try:

            payload = {
                "state": "active" if session.interactive_session else "inactive",
                "attributes": {
                    "interactive_session": session.interactive_session,
                    "user": session.user or "",
                    "uid": session.uid or 0,
                    "session": session.session or "",
                    "idle": session.idle,
                    "app": session.app or "",
                    "app_title": session.app_title or "",
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
