# config.py

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
import logging

logger = logging.getLogger(__name__)

@dataclass
class UserConfig:
    active_entity: str
    started_entity: str
    remaining_entity: str

@dataclass
class Config:
    ha_url: str
    ha_rest_url: str
    ha_poll_interval: int
    ha_desktop_state_entity: str
    token: str
    users: Dict[str, UserConfig]


path = Path(__file__).parent / "config.json"

def load_config(path="config.json") -> Config:

    path = Path(__file__).parent / path

    if not path.exists():
        logger.info(f"Config not found: {path}")
        raise FileNotFoundError(f"Config not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))

    #logger.info(data)
    
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
    
