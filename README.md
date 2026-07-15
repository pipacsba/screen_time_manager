# Screen Time Manager

An open-source screen time management solution for Linux desktops, tightly integrated with Home Assistant.

The project combines a lightweight Python background service, a GNOME Shell extension, and Home Assistant automations to provide a flexible and transparent screen time management system. Rather than enforcing limits locally, Home Assistant remains the central source of truth, making it easy to automate rewards, exemptions, schedules, and dashboards.

---

## Why this project?

Most existing parental-control solutions are closed ecosystems with limited automation capabilities.

This project takes a different approach:

* **Home Assistant is the brain.** All policies, rewards, schedules, and automations are managed in Home Assistant.
* **Linux remains in control of the desktop.** The local service only reports desktop activity, displays the remaining time, and enforces the configured limits.
* **Everything is transparent.** Every component is open source, configurable, and easy to extend.

The result is a solution that integrates naturally into an existing smart home instead of replacing it.

---

## Features

* Live screen time countdown in the desktop status bar.
* Home Assistant as the single source of truth.
* Automatic session detection.
* Real-time synchronization using Home Assistant WebSockets.
* Automatic recovery after reconnects or Home Assistant restarts.
* Configurable educational application exemptions.
* Reward system driven by Home Assistant automations.
* Daily allowance resets.
* Grace period before locking the desktop.
* Multi-user support.
* Modular architecture designed for extension.

---

## Architecture

```
                 Home Assistant
                        ▲
                        │
          WebSocket + REST synchronization
                        │
                        ▼
           Python Screen Time Service
                        │
          ┌─────────────┴─────────────┐
          │                           │
          ▼                           ▼
   Desktop Session             Waybar Status
      Discovery                 & Notifications
          │
          ▼
   Focused Window API
     (GNOME Extension)
```

The Python service continuously monitors the active desktop session, synchronizes the screen time state with Home Assistant, and updates the local desktop interface.

---

## Components

The repository contains several independent components:

* **Python backend** – monitors desktop sessions, synchronizes with Home Assistant, and manages the local countdown.
* **GNOME Shell extension** – displays the remaining time in the desktop panel.
* **Home Assistant package** – implements the screen time policy, rewards, and automations.
* **Focused Window GNOME extension** *(external dependency)* – exposes the currently focused application over D-Bus for educational application detection.

---

## Documentation

Detailed documentation is available in the `docs/` directory:

* `architecture.md` — Overall system architecture
* `python.md` — Python backend internals
* `homeassistant.md` — Home Assistant package
* `gnome-extension.md` — Tray extension
* `focused-window-extension.md` — External dependency
* `installation.md` — Installation guide
* `configuration.md` — Configuration reference
* `development.md` — Development notes

---

## Installation

See **`docs/installation.md`** for a complete installation guide.

---

## License

This project is licensed under the MIT License.
