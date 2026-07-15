# Configuration

The Screen Time Manager is intentionally designed to be configurable with minimal code changes.

Configuration is split into two independent parts:

- **Python configuration** (`config.json`) – connection to Home Assistant and mapping Linux users to Home Assistant entities.
- **Home Assistant configuration** – screen-time policies, rewards, automations, and dashboard entities.

---

# Python Configuration

The Python daemon loads its configuration from:

```
config.json
```

A template is provided:

```
config_template.json
```

Create your own configuration by copying the template:

```bash
cp config_template.json config.json
```

---

## Example

```json
{
  "ha_url": "ws://homeassistant.local:8123/api/websocket",
  "ha_rest_url": "http://homeassistant.local:8123/api",
  "ha_poll_interval": 30,
  "ha_desktop_state_entity": "sensor.desktop_session",
  "token": "YOUR_LONG_LIVED_ACCESS_TOKEN",

  "users": {
    "alice": {
      "active_entity": "input_boolean.alice_computer_time_active",
      "started_entity": "input_datetime.alice_computer_time_started",
      "remaining_entity": "sensor.alice_computer_time_remaining"
    },

    "bob": {
      "active_entity": "input_boolean.bob_computer_time_active",
      "started_entity": "input_datetime.bob_computer_time_started",
      "remaining_entity": "sensor.bob_computer_time_remaining"
    }
  }
}
```

---

## Configuration Fields

### Home Assistant

| Field | Description |
|--------|-------------|
| `ha_url` | Home Assistant WebSocket endpoint |
| `ha_rest_url` | Home Assistant REST API endpoint |
| `ha_poll_interval` | REST synchronization interval (seconds) |
| `ha_desktop_state_entity` | Entity used to publish desktop session information |
| `token` | Home Assistant Long-Lived Access Token |

---

### User Mapping

Each monitored Linux user must be mapped to the corresponding Home Assistant entities.

For every user, the daemon requires three entities:

| Entity | Purpose |
|---------|---------|
| `active_entity` | Indicates whether the countdown is currently running |
| `started_entity` | Stores when the current countdown started |
| `remaining_entity` | Live remaining computer time |

These entities are maintained by the Home Assistant package described in `homeassistant.md`.

---

# Monitoring Multiple Users

Adding another monitored user requires only two steps:

1. Create the corresponding Home Assistant helpers and automations.
2. Add another entry under `users` in `config.json`.

Example:

```json
"charlie": {
    "active_entity": "input_boolean.charlie_computer_time_active",
    "started_entity": "input_datetime.charlie_computer_time_started",
    "remaining_entity": "sensor.charlie_computer_time_remaining"
}
```

The daemon automatically detects user switches and starts the appropriate worker threads for the active user.

---

# Home Assistant Entity

The daemon also publishes information about the active desktop session.

Example:

```
sensor.desktop_session
```

Typical attributes include:

- logged-in user
- session ID
- idle state
- active application
- active window title

These attributes allow Home Assistant automations to react to desktop activity without any additional desktop-side configuration.

---

# Security Notes

The configuration file contains a **Home Assistant Long-Lived Access Token**.

For this reason:

- **Do not commit `config.json` to version control.**
- Commit only `config_template.json`.
- Add `config.json` to `.gitignore`.

Example:

```gitignore
config.json
```

---

# Recommended Directory Layout

```
screen_time_manager/
│
├── config_template.json
├── config.json          ← local only (ignored by Git)
│
├── main.py
├── service.py
├── countdown.py
├── homeassistant_ws.py
├── homeassistant_rest.py
│
└── docs/
```

This keeps deployment-specific information separate from the application source code.
