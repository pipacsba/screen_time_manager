# Architecture

## Overview

Screen Time Manager is built around a simple architectural principle:

> **Home Assistant defines the screen-time policy, while the Linux client enforces it locally.**

This separation keeps the desktop client lightweight and reusable, while allowing the screen-time rules to be implemented entirely using Home Assistant entities and automations.

---

# High-Level Architecture

```text
                         Home Assistant
                   (Policy & Automation Engine)
                               ▲
                               │
                  WebSocket + REST Synchronization
                               │
                               ▼
                  Python Screen Time Service
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
 Desktop Session         Countdown Logic      Desktop State
    Discovery           & Local Enforcement     Publishing
        │
        ▼
 Focused Window API
 (GNOME Shell Extension)
        │
        ▼
 GNOME Desktop

```

The Python service acts as the bridge between the Linux desktop and Home Assistant. It continuously discovers the active desktop session, synchronizes the current screen-time state with Home Assistant, and provides feedback to the user through the desktop environment.

---

# Component Responsibilities

## Home Assistant

Home Assistant is the **single source of truth**.

It stores the persistent screen-time state and defines the rules that determine:

* when computer time is consumed,
* when it is paused,
* which applications are exempt,
* how bonus time is earned,
* when daily allowances are reset,
* and how the remaining time is presented on dashboards.

The Linux client never decides these policies—it simply follows them.

---

## Python Service

The Python service is responsible for interacting with the operating system.

Its responsibilities include:

* discovering the active desktop session,
* identifying the logged-in user,
* obtaining the focused application,
* synchronizing with Home Assistant,
* displaying the remaining time,
* notifying the user,
* locking the desktop when required.

The service intentionally contains very little policy logic.

---

## GNOME Shell Extension

The included GNOME Shell extension is purely a user interface component.

It monitors the status file produced by the Python daemon and displays:

* remaining time,
* current mode (running or paused),
* tooltip information,
* status colors.

It performs no countdown calculations and never communicates with Home Assistant.

---

## Focused Window Extension

The project depends on an external GNOME Shell extension that exposes the currently focused application over D-Bus.

The Python service queries this information whenever the desktop session changes, allowing Home Assistant to distinguish between ordinary applications and educational software.

This dependency is intentionally isolated from the rest of the application.

---

# Runtime Flow

## 1. Session Discovery

The main thread periodically asks:

> "Who is currently using the desktop?"

The discovery process:

* enumerates login sessions,
* ignores SSH sessions,
* ignores idle sessions,
* verifies that a graphical D-Bus session exists,
* retrieves the focused application.

The result is represented as a `Session` object.

---

## 2. Desktop State Publishing

Whenever the session changes, the Python service publishes the desktop state to Home Assistant.

This includes:

* active user,
* session identifier,
* idle status,
* focused application,
* focused window title.

Home Assistant automations can immediately react to these changes.

---

## 3. Worker Lifecycle

Whenever a configured user logs in, the service starts a dedicated set of worker threads:

```text
Main Thread
    │
    ├── Countdown Thread
    ├── WebSocket Thread
    └── REST Thread
```

When the session ends or another user logs in:

* all workers are stopped,
* the WebSocket is closed,
* threads terminate gracefully,
* a new worker set is created for the new session.

Each worker set therefore belongs to exactly one desktop session.

---

# Synchronization Strategy

Home Assistant remains authoritative.

```text
Home Assistant
        │
        ▼
 WebSocket / REST
        │
        ▼
 Shared ComputerTime Model
        │
        ▼
 Countdown Display
```

Normally, changes arrive almost instantly over the WebSocket connection.

The REST synchronizer periodically refreshes the shared state to recover from:

* missed WebSocket events,
* temporary network failures,
* Home Assistant restarts.

This combination provides both responsiveness and resilience.

---

# Shared State

The worker threads communicate exclusively through a shared `ComputerTime` object.

```text
ComputerTime
 ├── lock
 ├── active
 ├── started
 ├── remaining_base
 └── bootstrap
```

All access is protected by a mutex to ensure thread safety.

No worker communicates directly with another worker.

---

# Thread Model

```text
                     Main Thread
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
 Countdown Thread   WebSocket Thread   REST Thread

              Shared ComputerTime Model
```

Each thread has a single responsibility.

The shared model acts as the only communication channel between them, minimizing synchronization complexity.

---

# Design Principles

The project follows several guiding principles.

## Home Assistant is the source of truth

Persistent state and automation rules belong in Home Assistant rather than in the desktop client.

---

## Separation of responsibilities

Each module performs one clearly defined task.

Examples include:

* session discovery,
* synchronization,
* countdown calculation,
* desktop presentation.

This makes the system easier to understand and maintain.

---

## Fail gracefully

Temporary failures should never terminate the service.

The application automatically recovers from:

* Home Assistant restarts,
* WebSocket disconnects,
* temporary network outages,
* desktop logouts,
* user switches.

---

## Desktop independence

The business logic is intentionally independent of GNOME.

Only two small integration points are desktop-specific:

* the Focused Window extension (desktop information),
* the panel extension (desktop presentation).

Everything else can be reused by another desktop environment with minimal changes.

---

# Repository Structure

```text
screen-time-manager/
│
├── python/
│   ├── main.py
│   ├── service.py
│   ├── countdown.py
│   ├── homeassistant_ws.py
│   ├── homeassistant_rest.py
│   └── ...
│
├── gnome-extension/
│
├── homeassistant/
│
├── docs/
│
└── README.md
```

The repository is organized around components rather than technologies, allowing each part of the system to evolve independently.
