# Python Backend

## Overview

The Python backend is the runtime component of Screen Time Manager.

It runs as a long-lived `systemd` service and acts as the bridge between the Linux desktop and Home Assistant.

Its responsibilities are intentionally limited:

* discover the active desktop session,
* synchronize screen-time state with Home Assistant,
* display the remaining time locally,
* enforce the configured time limit.

The Python service deliberately **does not decide** how much time a user should receive or when time should be rewarded. Those decisions belong entirely to Home Assistant.

---

# Runtime Overview

The application consists of a small number of cooperating modules.

```text
                 main.py
                    │
                    ▼
          Discover desktop session
                    │
          Starts worker threads
                    │
     ┌──────────────┼──────────────┐
     ▼              ▼              ▼
 countdown     WebSocket      REST Sync
     │              │              │
     └──────────────┼──────────────┘
                    ▼
          Shared ComputerTime Model
                    │
                    ▼
             status.json (Waybar)
```

The main thread owns the application lifecycle. All background work is delegated to worker threads.

---

# Module Responsibilities

## `main.py`

The application's entry point.

Responsibilities:

* load configuration,
* discover desktop sessions,
* publish desktop session state,
* create and destroy worker threads,
* handle user switches,
* manage application shutdown.

The main thread intentionally performs very little work itself. Its primary purpose is orchestration.

---

## `config.py`

Loads the JSON configuration and converts it into strongly typed Python objects.

Configuration includes:

* Home Assistant URLs,
* authentication token,
* synchronization interval,
* monitored users,
* Home Assistant entity mappings.

Parsing the configuration once during startup keeps the rest of the application independent from JSON.

---

## `service.py`

Provides all operating system integration.

Responsibilities include:

* discovering graphical login sessions,
* ignoring SSH and idle sessions,
* locating the user's D-Bus,
* querying the focused window,
* creating a `Session` object.

This module is intentionally isolated from Home Assistant and countdown logic.

---

## `model.py`

Defines the shared runtime state.

All worker threads communicate exclusively through a single `ComputerTime` instance protected by a mutex.

Keeping the model intentionally small minimizes synchronization complexity.

---

## `homeassistant_ws.py`

Maintains a persistent WebSocket connection to Home Assistant.

Responsibilities:

* authenticate,
* subscribe to entity changes,
* immediately update the shared model,
* automatically reconnect after connection loss.

The WebSocket provides near real-time synchronization.

---

## `homeassistant_rest.py`

Provides two independent functions.

### REST Synchronization

Periodically refreshes the shared model from Home Assistant.

This acts as a safety net if:

* WebSocket events are missed,
* Home Assistant restarts,
* the connection temporarily fails.

### Desktop State Publisher

Publishes desktop session information to Home Assistant whenever anything changes.

Published attributes include:

* active user,
* session identifier,
* idle state,
* focused application,
* focused window title.

This information is consumed by Home Assistant automations.

---

## `countdown.py`

Implements the local countdown logic.

Responsibilities:

* calculate the remaining time,
* update the desktop status,
* display notifications,
* manage the grace period,
* lock the desktop when necessary.

The countdown thread never communicates directly with Home Assistant.

It only consumes the shared model.

---

## `status.py`

Provides a small abstraction around the status file consumed by the GNOME Shell extension.

Updates are written atomically to avoid the extension reading partially written JSON.

---

## `logger.py`

Configures application logging.

Centralizing logging configuration ensures that every module follows the same logging format and verbosity.

---

# Worker Threads

Each active desktop session owns three worker threads.

## Countdown Thread

Runs once per second.

Responsible for:

* calculating remaining time,
* updating the status file,
* sending notifications,
* locking the desktop.

---

## WebSocket Thread

Maintains a permanent Home Assistant WebSocket connection.

Provides low-latency updates whenever Home Assistant changes the screen-time state.

---

## REST Thread

Runs periodically.

Its purpose is not speed, but consistency.

Even if the WebSocket temporarily disconnects, the REST thread eventually restores the correct state.

---

# Shared Model

The worker threads never communicate directly.

Instead they share a single `ComputerTime` object.

```text
ComputerTime
 ├── lock
 ├── active
 ├── started
 ├── remaining_base
 └── bootstrap
```

The model intentionally contains only the information required to calculate the countdown.

Everything else remains in Home Assistant.

---

# Synchronization Strategy

The backend follows a simple synchronization model.

```text
          Home Assistant
                 │
      WebSocket / REST
                 │
                 ▼
        ComputerTime Model
                 │
                 ▼
          Countdown Thread
                 │
                 ▼
          Desktop Status File
```

Home Assistant always remains authoritative.

The desktop application only performs short-lived optimistic updates (for example immediately after locking the screen), which are later overwritten by the authoritative Home Assistant state.

---

# Desktop Session Discovery

Session discovery is performed continuously.

The discovery process:

1. Enumerates active login sessions using `loginctl`.
2. Ignores SSH sessions.
3. Ignores idle sessions.
4. Verifies that the session owns a graphical D-Bus.
5. Queries the focused application from the external Focused Window extension.
6. Builds a `Session` object.

The rest of the application never interacts directly with operating system commands.

---

# Worker Lifecycle

Workers are tied to the currently active desktop session.

When:

* a configured user logs in,
* another configured user becomes active,
* or the desktop session ends,

the existing workers are stopped and a new set is created if necessary.

This guarantees that every worker always operates on exactly one desktop session.

---

# Error Handling

The backend is designed to recover automatically from common failures.

Examples include:

* temporary Home Assistant outages,
* WebSocket disconnects,
* desktop logouts,
* user switches,
* transient REST failures.

Recoverable errors are logged, but they do not terminate the service.

The only expected way to stop the application is through the service manager or a user interrupt during development.

---

# Design Principles

The Python backend follows several principles.

## Home Assistant owns the policy

The backend never decides how much time remains or when rewards should be granted.

Its responsibility is limited to synchronization and local enforcement.

---

## Single Responsibility

Each module performs one clearly defined task.

This keeps dependencies low and makes future changes easier.

---

## Shared State is Minimal

The shared model intentionally contains only the minimum information necessary for the countdown.

Everything else remains in Home Assistant.

---

## Recover Automatically

The backend assumes that network failures and reconnects are normal.

Rather than failing, it continually attempts to resynchronize and return to a consistent state.

---

## Platform Integration is Isolated

All operating-system-specific code lives inside `service.py`.

This makes the remainder of the application largely independent from the underlying desktop environment and simplifies future ports to other Linux desktops.
