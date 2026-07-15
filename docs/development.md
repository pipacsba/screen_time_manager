# Development Guide

This document is intended for contributors who want to understand or extend the project.

---

# Design Philosophy

The project intentionally separates responsibilities into independent components.

- **Home Assistant** owns the screen-time policy and remains the single source of truth.
- **Python** acts as the synchronization and desktop integration layer.
- **GNOME Shell** is responsible only for user interface.
- **Focused Window Extension** exposes desktop information through a simple D-Bus API.

Each component can evolve independently.

---

# Repository Layout

```
screen_time_manager/
├── README.md
├── docs/
│   ├── architecture.md
│   ├── installation.md
│   ├── configuration.md
│   ├── python.md
│   ├── gnome-extension.md
│   ├── focused-window-extension.md
│   ├── homeassistant.md
│   └── development.md
│
├── main.py
├── config.py
├── model.py
├── service.py
├── countdown.py
├── homeassistant_ws.py
├── homeassistant_rest.py
├── status.py
├── logger.py
│
├── config_template.json
├── requirements.txt
│
├── extension/
│   └── ha-monitor@local/
│
└── homeassistant/
    └── computer_time.yaml
```

---

# Thread Model

The Python daemon intentionally uses a very small number of threads.

```
                 Main Thread
                      │
      ┌───────────────┼───────────────┐
      │               │               │
      ▼               ▼               ▼
 Countdown      WebSocket       REST Sync
```

Only one object is shared:

```
ComputerTime
```

Access is synchronized with a mutex.

No other shared state exists.

---

# Synchronization Strategy

Home Assistant is always considered authoritative.

```
Home Assistant
        │
        ▼
WebSocket / REST
        │
        ▼
 ComputerTime
        │
        ▼
 Countdown
```

The countdown thread never computes policy.

It simply presents the state supplied by Home Assistant.

Temporary optimistic updates (for example after locking the screen) are automatically overwritten during the next synchronization.

---

# Coding Style

The project intentionally follows a conservative coding style.

## Small modules

Each file has one responsibility.

Examples:

- `service.py` only discovers desktop sessions.
- `status.py` only writes the Waybar JSON.
- `countdown.py` only handles countdown display.

---

## Why-oriented comments

Comments explain **why** something exists rather than describing what the code already says.

Prefer:

```python
#
# Home Assistant remains the authoritative source.
# The optimistic update only prevents displaying stale values
# until the next synchronization.
#
```

Avoid:

```python
# Set active to False
model.active = False
```

---

## Explicit names

Names should be descriptive.

Good:

```
remaining_base
publish_desktop_state
interactive_session
```

Avoid abbreviations unless they are universally understood.

---

## Logging

Unexpected situations should be logged.

Recoverable failures should not terminate the service.

Examples include:

- temporary Home Assistant outages
- broken WebSocket connections
- unavailable D-Bus services

The daemon is expected to recover automatically whenever possible.

---

# Adding Support for Another Desktop Environment

Only `service.py` depends on GNOME-specific functionality.

To support another desktop environment, the new implementation only needs to provide equivalent information:

- active user
- session state
- focused application
- window title

The rest of the application can remain unchanged.

---

# Adding Another Child

Supporting additional users requires only configuration changes.

## Python

Add another user to:

```
config.json
```

with the corresponding Home Assistant entities.

## Home Assistant

Create another set of:

- `input_boolean`
- `input_datetime`
- `input_number`

Duplicate the template entities and automations for the new child.

No code changes are required.

---

# Testing

Useful commands during development:

Run manually:

```bash
python3 main.py
```

Check logs:

```bash
journalctl --user -u screen_time_manager.service -f
```

Inspect the published desktop sensor:

```
Developer Tools
→ States
→ sensor.desktop_session
```

Verify the focused-window D-Bus service:

```bash
gdbus call \
  --session \
  --dest org.gnome.shell.extensions.FocusedWindow \
  --object-path /org/gnome/shell/extensions/FocusedWindow \
  --method org.gnome.shell.extensions.FocusedWindow.Get
```

---

# Future Ideas

Potential improvements include:

- Support for KDE Plasma.
- Configurable grace period.
- Configurable notification messages.
- Generic multi-user Home Assistant package generation.
- Unit tests for countdown and session discovery.
- Optional event-driven session monitoring instead of polling.
- Packaging as a Python package (`pip` installable).
- Automatic installation of the GNOME extension.

---

# Contributing

Contributions are welcome.

When submitting changes, please try to keep the following principles:

- Keep modules focused on a single responsibility.
- Preserve Home Assistant as the source of truth.
- Prefer simple solutions over clever ones.
- Add comments that explain *why*, not *what*.
- Keep the desktop integration independent from the automation logic.

Maintaining these design principles keeps the project easy to understand, extend, and debug.
