# Home Assistant Package

## Overview

The Home Assistant package implements the **screen-time policy** for Screen Time Manager.

Unlike the Python backend, which is responsible for interacting with the Linux desktop, the Home Assistant package defines:

- how much computer time is available,
- when the countdown starts and stops,
- which activities are exempt,
- how rewards are earned,
- when allowances are reset.

In other words:

> **Home Assistant is the brain. The Linux client is the hands.**

---

# Design Philosophy

The package was intentionally designed around persistent helper entities rather than Home Assistant's built-in `timer` integration.

Each child's remaining allowance is stored as a persistent value that survives:

- Home Assistant restarts
- Linux restarts
- network outages
- temporary disconnects

The live countdown is **calculated**, not stored.

---

# Architecture

```
                    Home Assistant

             Persistent Helper Entities
          ┌──────────┬──────────┬──────────┐
          │          │          │          │
          ▼          ▼          ▼
     Active      Started     Remaining Base
          │
          │
          ▼
     Template Sensors
          │
          ▼
      Automations
          │
          ▼
     Python Service
```

The Python service simply follows the state exposed by Home Assistant.

---

# Persistent State

Each monitored user owns three helper entities.

## Active

```
input_boolean
```

Indicates whether computer time is currently being consumed.

```
ON  -> countdown running

OFF -> countdown paused
```

---

## Started

```
input_datetime
```

Stores the timestamp when the current session began.

---

## Remaining Base

```
input_number
```

Stores the remaining computer allowance in seconds.

Unlike a traditional timer, this value is **not updated every second**.

It changes only when:

- the countdown is paused,
- bonus time is awarded,
- the daily allowance is reset.

This dramatically reduces writes to Home Assistant's database.

---

# Live Countdown

The remaining time is calculated dynamically.

```
remaining =
remaining_base
-
(now - started)
```

As long as the countdown is active, the template sensor automatically updates because it references `now()`.

The persistent helper remains unchanged.

This approach provides:

- live updates
- minimal database writes
- automatic recovery after restarts

---

# Template Entities

The package exposes several template entities.

## Active Computer Session

Determines whether a child is actively using the computer.

Typical conditions include:

- correct logged-in user
- session is not idle

---

## Exempt Window

Determines whether the currently focused application should consume computer time.

Rules are defined declaratively.

Example:

```yaml
- app: tuxmath

- app: org.gnome.Epiphany
  title_contains: Duolingo
```

Adding another educational application simply means adding another rule.

---

## Remaining Time

The live countdown sensor.

Provides:

- remaining seconds
- formatted HH:MM:SS representation
- active/paused status

This is the entity typically displayed on dashboards.

---

# Scripts

The package implements a small state machine through reusable scripts.

---

## computer_time_start

Starts consuming computer time.

Actions:

- enable countdown
- record session start time

---

## computer_time_pause

Stops consuming computer time.

Actions:

- calculate elapsed time
- permanently store the remaining allowance
- disable countdown

---

## computer_time_reward

Adds bonus computer time.

The value is automatically limited by the configured maximum.

Rewards may be granted while the countdown is either running or paused.

---

## computer_time_reset

Restores the daily allowance.

Actions:

- stop countdown
- restore configured allowance
- reset the start timestamp

---

# Automations

The package uses automations to implement the screen-time policy.

---

## Countdown Control

The primary automation decides whether computer time should currently be consumed.

The countdown starts when:

- the correct child is logged in,
- the session is active,
- the current application is not exempt.

Otherwise it is paused.

The automation itself contains very little logic because the reusable scripts perform the actual state transitions.

---

## Reward System

Additional computer time can be awarded automatically.

Each monitored sensor defines:

- a minimum change threshold,
- a reward amount.

For example:

```
Duolingo XP
        │
        ▼
XP increased by 10
        │
        ▼
+15 minutes
```

Additional reward sources can be added simply by extending the threshold dictionary.

---

## Daily Reset

Once per day:

- active sessions are stopped,
- the daily allowance is restored,
- a fresh countdown begins the next time the child logs in.

---

# Interaction with the Python Service

The Python backend consumes three entities:

- active
- started
- remaining

Whenever Home Assistant changes one of them:

```
Automation
        │
        ▼
Helper Entity
        │
        ▼
WebSocket Event
        │
        ▼
Python Backend
        │
        ▼
Desktop Countdown
```

The Python service never modifies the policy itself.

---

# Desktop Session Entity

The package expects the Python service to publish a desktop session entity.

Typical attributes include:

- logged-in user
- idle state
- focused application
- focused window title

Automations use these attributes to determine whether computer time should currently be consumed.

---

# Adding Another Child

Supporting another child requires only a few additions.

1. Create helper entities:

- input_boolean
- input_datetime
- input_number

2. Duplicate the template sensors.

3. Duplicate the countdown automation.

4. Configure the Python service to monitor the new Linux user.

The package was intentionally designed so each child's configuration remains independent.

---

# Why Not Use Home Assistant Timers?

The built-in `timer` integration was intentionally not used.

Reasons include:

- timer state is less convenient to manipulate
- adding or subtracting time is cumbersome
- persistence is more limited
- extending the logic becomes more complex

Using helper entities keeps the implementation transparent and flexible.

---

# Design Principles

The Home Assistant package follows several principles.

## Home Assistant Owns the Policy

The Linux client never decides:

- when time starts,
- when it stops,
- who receives rewards,
- which applications are exempt.

Everything is implemented through Home Assistant.

---

## State is Persistent

Only the minimum required state is stored.

Everything else is derived.

---

## Automations Stay Simple

Complex calculations are delegated to reusable scripts and template entities.

Each automation simply decides **when** an action should occur.

---

## Easy to Extend

The package was designed to make common changes straightforward:

- add another child,
- add another educational application,
- create another reward source,
- modify daily allowances,
- change reset schedules.

Most customizations require configuration changes rather than code changes.
