#
# Configuration loader
#
# Reads config.json and converts it into strongly typed dataclasses.
#
# The configuration consists of:
#
#   - Home Assistant connection settings
#   - Desktop state entity used by the system service
#   - Per-user Home Assistant entities used for screen-time monitoring
#
# Unlike earlier versions, this service runs system-wide, so it loads the
# configuration for all monitored users. The active desktop session is
# determined at runtime, and the appropriate UserConfig is selected later.
#

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class UserConfig:
    """
    Home Assistant entities belonging to one monitored desktop user.
    """

    active_entity: str
    started_entity: str
    remaining_entity: str


@dataclass
class Config:
    """
    Complete application configuration loaded from config.json.
    """

    ha_url: str
    ha_rest_url: str
    ha_poll_interval: int
    ha_desktop_state_entity: str
    token: str
    users: Dict[str, UserConfig]


def load_config(path: str = "config.json") -> Config:
    """
    Load the application configuration from disk.

    Returns:
        Config object containing the global configuration and all configured
        users.
    """

    path = Path(__file__).parent / path

    if not path.exists():
        logger.error("Config not found: %s", path)
        raise FileNotFoundError(f"Config not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    users = {
        username: UserConfig(
            active_entity=user["active_entity"],
            started_entity=user["started_entity"],
            remaining_entity=user["remaining_entity"],
        )
        for username, user in data["users"].items()
    }

    return Config(
        ha_url=data["ha_url"],
        ha_rest_url=data["ha_rest_url"],
        ha_poll_interval=data["ha_poll_interval"],
        ha_desktop_state_entity=data["ha_desktop_state_entity"],
        token=data["token"],
        users=users,
    )
