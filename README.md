---
# HA Screen Time Monitor

## Overview

HA Screen Time Monitor is a lightweight desktop companion for Home Assistant.

Its primary purpose is to:

- display the remaining computer time in the desktop status bar (Waybar),
- keep the countdown synchronized with Home Assistant,
- enforce the configured time limit by locking the desktop after a configurable grace period,
- publish information about the active desktop session back to Home Assistant.

The application is designed as a long-running **systemd service** that continuously follows the currently active graphical user session.


---

# High-Level Architecture

```
                  +----------------------+
                  |      Home Assistant  |
                  |                      |
                  |  WebSocket   REST    |
                  +-----------+----------+
                              ^
                 Sync state    | Publish desktop state
                              |
             +----------------+----------------+
             |                                 |
             |     HA Screen Time Monitor      |
             |                                 |
             |  +--------------------------+   |
             |  |       Main Loop          |   |
             |  +------------+-------------+   |
             |               |                 |
             |               | discovers       |
             |               v                 |
             |      Desktop Session            |
             |                                 |
             |  starts/stops worker threads    |
             +-------+------------+------------+
                     |            |
                     |            |
         +-----------+            +-----------+
         |                                    |
         v                                    v

 +-------------------+              +-------------------+
 | HomeAssistant WS  |              | HomeAssistant REST|
 |                   |              |                   |
 | receives updates  |              | polling fallback  |
 +---------+---------+              +---------+---------+
           |                                  |
           +---------------+------------------+
                           |
                           v
                   Shared ComputerTime Model
                           |
                           v
                     Countdown Thread
                           |
                           |
              +------------+------------+
              |                         |
              v                         v
       Waybar status.json         Notifications
                                  Screen locking
```

---

# Runtime Flow

## 1. Session discovery

The main thread periodically asks:

> "Who is currently using the desktop?"

This is performed by `service.py`.

The discovery process:

- enumerates all login sessions (`loginctl`)
- ignores SSH sessions
- ignores idle sessions
- verifies the user owns a desktop D-Bus
- retrieves the currently focused application from GNOME Shell

The result is represented by a `Session` object.

---

## 2. Publishing desktop information

Whenever anything about the session changes, the monitor publishes the current desktop state to Home Assistant.

Published information includes:

- logged in user
- session id
- active application
- active window title
- idle status

This allows Home Assistant automations to react to desktop activity.

---

## 3. Worker lifecycle

Whenever a configured user becomes active:

```
Main
    │
    ├── Countdown thread
    ├── WebSocket thread
    └── REST synchronization thread
```

When the user logs out or another user logs in:

- all workers are stopped
- the WebSocket is closed
- threads are joined
- a new set of workers is created for the new session

Workers are therefore always tied to exactly one desktop session.

---

# Worker Responsibilities

## Main Thread

Responsible for:

- session discovery
- worker creation/destruction
- publishing desktop state
- handling user switches

The main thread intentionally performs very little work.

---

## WebSocket Thread

Maintains a persistent Home Assistant WebSocket connection.

Responsibilities:

- authenticate
- subscribe to entity changes
- immediately update the shared model

This is the preferred synchronization mechanism because updates arrive almost instantly.

---

## REST Thread

Acts as a safety net.

Responsibilities:

- periodically read the authoritative state from Home Assistant
- recover after missed WebSocket events
- recover after reconnects

Even if the WebSocket temporarily disconnects, the countdown eventually resynchronizes.

---

## Countdown Thread

Runs once per second.

Responsibilities:

- calculate remaining time
- update Waybar
- send desktop notifications
- start the grace period
- lock the session when the grace period expires

This thread never communicates directly with Home Assistant.

It only consumes the shared model.

---

# Shared Model

All worker threads share a single `ComputerTime` instance.

```
ComputerTime
 ├── active
 ├── started
 ├── remaining_base
 └── bootstrap
```

Access is protected by a mutex.

The model intentionally contains only the minimum state necessary to compute the countdown.

---

# Synchronization Strategy

Home Assistant remains the single source of truth.

```
Home Assistant
        │
        │
        ▼
 WebSocket / REST
        │
        ▼
 ComputerTime model
        │
        ▼
 Countdown display
```

The desktop application performs only short-lived optimistic updates (for example immediately after locking the screen).

These are later overwritten by the authoritative values received from Home Assistant.

---

# Status Output

The countdown thread periodically writes

```
status.json
```

into

```
/run/user/<uid>/ha-time/
```

Example:

```json
{
  "version": 1,
  "text": "🎮 00:23:15",
  "tooltip": "Computer time remaining",
  "color": "green"
}
```

The file is written atomically to prevent Waybar from reading partially written JSON.

---

# Design Principles

The application follows several design principles:

- Home Assistant is the source of truth.
- Each module has a single responsibility.
- Desktop session detection is isolated from Home Assistant logic.
- Worker threads communicate only through a shared model.
- The main thread owns worker lifetime.
- Failures should degrade gracefully rather than terminate the service.
- The service should automatically recover from:
  - WebSocket disconnects
  - temporary Home Assistant outages
  - desktop logouts
  - user switches

---

# Module Responsibilities

| Module | Responsibility |
|---------|----------------|
| `main.py` | Application lifecycle and worker management |
| `service.py` | Desktop session discovery |
| `config.py` | Load configuration |
| `model.py` | Shared thread-safe state |
| `homeassistant_ws.py` | Real-time synchronization |
| `homeassistant_rest.py` | REST synchronization and state publishing |
| `countdown.py` | Countdown logic, notifications and screen locking |
| `status.py` | Publish Waybar status JSON |
| `logger.py` | Logging configuration |

---

# Thread Model

```
                     Main Thread
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
 Countdown Thread   WebSocket Thread   REST Thread

              Shared ComputerTime Model
```

Only the shared model is accessed concurrently.

Everything else is thread-local.

This keeps synchronization simple while allowing each worker to operate independently.

# GNOME Shell Extension

## Overview

The GNOME Shell extension provides a small bridge between the desktop and the
Python background service.

Its only responsibility is to expose information about the currently focused
window over D-Bus. The Python service queries this information periodically and
publishes it to Home Assistant.

Keeping the desktop-specific logic inside the extension keeps the Python code
desktop-agnostic and avoids depending on GNOME Shell internals.

---

## Responsibilities

The extension is responsible for:

- Tracking the currently focused application.
- Tracking the title of the active window.
- Exposing this information over D-Bus.
- Updating the exported data whenever the focused window changes.

The extension is **not** responsible for:

- Home Assistant communication.
- Screen time calculations.
- Waybar integration.
- Session detection.
- Business logic.

---

## Architecture

```
                    GNOME Shell
                         │
                         │ Window focus changes
                         ▼
                Extension JavaScript
                         │
                         │ Updates cached values
                         ▼
                  D-Bus Service
org.gnome.shell.extensions.FocusedWindow
                         ▲
                         │
                         │ gdbus call
                         │
                  Python service
```

---

## D-Bus API

The extension exports a single method:

```
Get()
```

which returns a JSON object similar to:

```json
{
  "app": "firefox",
  "title": "Home Assistant Dashboard"
}
```

The JSON is wrapped by `gdbus` as a D-Bus string, so the Python service removes
the wrapper before parsing it.

---

## Event Flow

```
User changes window
        │
        ▼
GNOME Shell notifies extension
        │
        ▼
Extension updates internal state
        │
        ▼
Python polls Get()
        │
        ▼
Desktop state published to Home Assistant
```

---

## Why D-Bus?

Using D-Bus has several advantages:

- No files need to be written.
- No polling inside the extension.
- The extension remains completely isolated from Home Assistant.
- Python can request information only when needed.
- Multiple clients could consume the same API in the future.

---

## Separation of Responsibilities

### JavaScript (GNOME Shell)

Responsible for:

- interacting with GNOME Shell APIs
- detecting focused windows
- exporting information via D-Bus

### Python

Responsible for:

- discovering active desktop sessions
- querying the D-Bus service
- publishing desktop state to Home Assistant
- synchronizing screen-time data
- updating Waybar

---

## Design Philosophy

The extension intentionally remains very small.

It acts purely as a **desktop information provider**, while all business logic
lives in Python. This separation makes each component easier to understand,
test, and maintain.

```
GNOME Shell
    │
    └── "What window is active?"

Python
    │
    └── "What should I do with that information?"

Home Assistant
    │
    └── "Automate based on the published state."
```

Future desktop integrations (e.g. KDE Plasma or another desktop environment)
could implement the same simple interface without requiring changes to the rest
of the system.

# Home Assistant Integration

The Home Assistant package implements the **screen time policy** independently of the Linux client.

Rather than relying on Home Assistant's `timer` integration, it maintains a persistent **computer time wallet** for each child.

### Design

Each child has three persistent helpers:

- `input_boolean` — whether the countdown is currently running
- `input_datetime` — when the current session started
- `input_number` — remaining allowance in seconds

While the countdown is active, the remaining time is calculated dynamically as:

```
remaining = remaining_base - (now - started)
```

The stored helper is only updated when the session is paused, rewarded, or reset—not every second. This minimizes database writes while keeping the displayed countdown live.

### Features

The package provides:

- automatic start/pause of the countdown based on desktop activity
- configurable application exemptions (e.g. educational software)
- reward mechanisms for learning achievements
- daily allowance reset
- live remaining-time sensor for dashboards
- reusable scripts for starting, pausing, rewarding, and resetting computer time

### Desktop Session

The package expects a `sensor.desktop_session` entity to be available.

This entity is provided by the accompanying Python service and contains information such as:

- logged-in user
- idle state
- active application
- active window title

The automations use these attributes to determine whether computer time should currently be consumed.

### Extending

Supporting additional children is straightforward:

1. Create another set of helpers (`input_boolean`, `input_datetime`, `input_number`).
2. Duplicate the template sensors.
3. Add the child's automations.
4. Configure the Python daemon to monitor the new user.

The package is intentionally modular so the Home Assistant logic remains independent of the Linux implementation.


# 🚀 Installation & Setup

### Prerequisites
Make sure you have Python (version 3.12+) installed and are running a GNOME-based Linux distribution (such as Ubuntu/Edubuntu).

---

### 1. General Setup & Python Backend

1. **Clone the repository and enter the directory:**
   ```bash
   cd /srv/venv/ha_tray/screen_time_manager
   ```

2. **Install the required Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the application:**
   Copy the template configuration file to create your active configuration:
   ```bash
   cp config_template.json config.json
   ```
   Open `config.json` in your text editor and fill in your Home Assistant URL, Long-Lived Access Token (LLAT), and your desired limits/entity configurations.

---

### 2. Run as a Systemd Service

To ensure the screen time daemon starts automatically when you log into your Linux computer, set it up as a user-level systemd service.

1. **Create the user systemd service directory (if it doesn't exist):**
   ```bash
   mkdir -p ~/.config/systemd/user/
   ```

2. **Create a service file:**
   Create a file named `~/.config/systemd/user/screentime.service` and add the following content:
   ```ini
   [Unit]
   Description=Screen Time Manager Daemon
   After=network.target

   [Service]
   Type=simple
   WorkingDirectory=/srv/venv/ha_tray/screen_time_manager
   ExecStart=/usr/bin/python3 /srv/venv/ha_tray/screen_time_manager/main.py
   Restart=on-failure

   [Install]
   WantedBy=default.target
   ```
   *(Ensure `/usr/bin/python3` points to your correct Python installation or virtual environment binary).*

3. **Enable and start the service:**
   ```bash
   systemctl --user daemon-reload
   systemctl --user enable screentime.service
   systemctl --user start screentime.service
   ```

4. **Verify it is running:**
   ```bash
   systemctl --user status screentime.service
   ```

---

### 3. Install the GNOME Shell Extension

The visual status indicator is packaged inside the repository under the `user/` directory layout.

1. **Copy the extension directory to your local GNOME extensions directory:**
   ```bash
   mkdir -p ~/.local/share/gnome-shell/extensions/
   cp -r user/.local/share/gnome-shell/extensions/ha-monitor@local ~/.local/share/gnome-shell/extensions/
   ```

2. **Restart GNOME Shell:**
   * **Under X11:** Press `Alt` + `F2`, type `r`, and press `Enter`.
   * **Under Wayland:** Log out of your desktop session and log back in.

3. **Enable the Extension:**
   Open your terminal and enable it directly:
   ```bash
   gnome-extensions enable ha-monitor@local
   ```
   *(Alternatively, you can manage and turn it on using the **Extensions** or **Extension Manager** graphical application).*

---

## ⚙️ Configuration File (`config.json`)

Ensure your `config.json` resembles the parameters defined in `config_template.json`:

```json
{
  "homeassistant_url": "http://YOUR_HA_IP:8123",
  "token": "YOUR_LONG_LIVED_ACCESS_TOKEN",
  "update_interval": 10
}
```

## 📄 License
This project is licensed under the [MIT License](LICENSE).
