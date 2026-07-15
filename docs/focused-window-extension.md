# Focused Window GNOME Extension

## Overview

Screen Time Manager relies on an external GNOME Shell extension to determine which application the user is currently interacting with.

This extension is **not part of this project**. It is an external dependency that exposes the currently focused application and window title over the user's D-Bus session.

The Python backend consumes this information and publishes it to Home Assistant, where it can be used by automations—for example, to exempt educational applications from consuming screen time.

---

# Why is it needed?

Linux does not provide a simple desktop-independent API for retrieving the currently focused application.

GNOME Shell already has this information internally, but it is not normally exposed to external applications.

The Focused Window extension bridges this gap by publishing the information through a simple D-Bus interface that any application can query.

---

# Architecture

```text
                GNOME Shell
                      │
                      │ Focus changes
                      ▼
      Focused Window GNOME Extension
                      │
                      │ D-Bus API
                      ▼
   org.gnome.shell.extensions.FocusedWindow
                      ▲
                      │
                      │ gdbus call
                      │
             Python Screen Time Service
                      │
                      ▼
              Home Assistant
```

The extension is completely independent from Screen Time Manager.

It simply answers the question:

> **"Which window currently has focus?"**

---

# D-Bus API

The extension exposes a single method:

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

Because the response is transported over D-Bus, `gdbus` wraps the JSON as a D-Bus string. The Python backend removes this wrapper before parsing the JSON.

---

# How Screen Time Manager Uses It

Whenever the Python backend discovers an active desktop session, it queries the extension.

The returned information is added to the desktop session state published to Home Assistant.

Typical published attributes include:

* current application,
* current window title,
* logged-in user,
* idle status,
* session identifier.

Home Assistant automations can then decide whether the current activity should consume computer time.

---

# Example Use Cases

The focused application information enables policies such as:

* educational applications do not consume screen time,
* learning websites are exempt,
* games consume normal allowance,
* different applications can receive different rewards.

For example:

```text
TuxMath
    ↓
Pause countdown

Firefox + Duolingo
    ↓
Pause countdown

Steam
    ↓
Continue countdown
```

The policy itself is implemented entirely in Home Assistant.

The extension simply provides the information required to make those decisions.

---

# Separation of Responsibilities

## Focused Window Extension

Responsible for:

* detecting the currently focused application,
* detecting the active window title,
* exposing this information through D-Bus.

It has no knowledge of:

* Home Assistant,
* screen time,
* rewards,
* countdowns,
* desktop locking.

---

## Python Backend

Responsible for:

* querying the D-Bus service,
* publishing the information to Home Assistant,
* synchronizing desktop state.

---

## Home Assistant

Responsible for:

* deciding whether the application is exempt,
* pausing or resuming the countdown,
* awarding bonus time,
* implementing the overall screen-time policy.

---

# Why D-Bus?

Using D-Bus offers several advantages:

* no temporary files,
* no polling inside the GNOME extension,
* standard desktop IPC mechanism,
* multiple applications can consume the same information,
* complete separation between desktop integration and business logic.

The Python service requests the information only when needed, keeping the extension lightweight and efficient.

---

# Installation

Since this extension is maintained independently, it must be installed separately before using Screen Time Manager.

After installation, the Python backend expects the following D-Bus service to be available:

```
org.gnome.shell.extensions.FocusedWindow
```

If the service is unavailable, Screen Time Manager continues to function, but application-aware features (such as educational application exemptions) will not be available.

---

# Design Philosophy

This extension intentionally remains outside the Screen Time Manager project.

Its purpose is generic desktop integration rather than screen-time management.

Keeping it as a separate dependency provides several advantages:

* it can be reused by unrelated projects,
* Screen Time Manager remains focused on screen-time management,
* desktop integration can evolve independently,
* alternative implementations (or support for other desktop environments) can be substituted without modifying the rest of the system.

In short, the extension answers **"What application is active?"**, while Screen Time Manager decides **"What should happen because of that?"**
