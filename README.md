# Screen Time Manager[cite: 1]

An automated screen time tracking and management utility for Linux systems. This application monitors user active session states and communicates screen time limits, statuses, and countdowns directly with **Home Assistant** while displaying a status indicator in the GNOME desktop panel.

---

## 🎯 Objective

The main goal of this project is to manage, monitor, and regulate user screen time on a Linux workstation. 

By running a background service that watches local session states, the system pushes real-time countdown updates to **Home Assistant** over WebSockets and REST APIs. Simultaneously, it provides the local user with visual tracking of their remaining screen time via a custom **GNOME Shell extension**.

---

## 🏗️ Architecture[cite: 1]

The application is split into two primary layers: a system-level tracking daemon and a desktop-level visual indicator.

```text
 ┌─────────────────────────────────────────────────────────┐
 │                      Linux OS                           │
 │                                                         │
 │  ┌──────────────────┐            ┌───────────────────┐  │
 │  │  systemd Service │            │  GNOME Shell      │  │
 │  │ (Python Daemon)  │            │  Extension        │  │
 │  └──────────┬───────┘            └─────────┬─────────┘  │
 └─────────────┼──────────────────────────────┼────────────┘
               │                              │
               │ (REST / WebSockets)          │ (Local State/API)
               ▼                              ▼
 ┌─────────────────────────────────────────────────────────┐
 │                    Home Assistant                       │
 │        (Tracks time limits, triggers, entities)         │
 └─────────────────────────────────────────────────────────┘
```

### Components[cite: 1]:
*   **Python Backend Daemon (`main.py`):** Runs persistently in the background as a user-level `systemd` service[cite: 1]. It tracks local active sessions, manages countdown timers, and syncs status updates.
*   **Home Assistant Connectors (`homeassistant_ws.py` & `homeassistant_rest.py`):** Maintain active connections to your Home Assistant instance, allowing bi-directional state tracking and automation triggers[cite: 1].
*   **GNOME Shell Extension (`ha-monitor@local`):** Displays a live, lightweight status indicator directly in the top panel bar of your GNOME desktop environment[cite: 1].

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

# 🚀 Installation & Setup[cite: 1]

### Prerequisites
Make sure you have Python (version 3.12+) installed and are running a GNOME-based Linux distribution (such as Ubuntu/Edubuntu).

---

### 1. General Setup & Python Backend[cite: 1]

1. **Clone the repository and enter the directory:**
   ```bash
   cd /srv/venv/ha_tray/screen_time_manager
   ```

2. **Install the required Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the application:**
   Copy the template configuration file to create your active configuration[cite: 1]:
   ```bash
   cp config_template.json config.json
   ```
   Open `config.json` in your text editor and fill in your Home Assistant URL, Long-Lived Access Token (LLAT), and your desired limits/entity configurations.

---

### 2. Run as a Systemd Service[cite: 1]

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

### 3. Install the GNOME Shell Extension[cite: 1]

The visual status indicator is packaged inside the repository under the `user/` directory layout[cite: 1].

1. **Copy the extension directory to your local GNOME extensions directory[cite: 1]:**
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

## ⚙️ Configuration File (`config.json`)[cite: 1]

Ensure your `config.json` resembles the parameters defined in `config_template.json`[cite: 1]:

```json
{
  "homeassistant_url": "http://YOUR_HA_IP:8123",
  "token": "YOUR_LONG_LIVED_ACCESS_TOKEN",
  "update_interval": 10
}
```

## 📄 License[cite: 1]
This project is licensed under the [MIT License](LICENSE)[cite: 1].
