# Installation

This document describes how to install the complete Screen Time Manager system.

The project consists of four independent components:

1. Home Assistant package
2. Python backend service
3. GNOME panel extension (tray countdown)
4. Focused Window GNOME extension (dependency)

All four components are required for the complete experience.

---

# Prerequisites

The project currently targets:

- Linux
- GNOME Shell
- Waybar
- Home Assistant
- Python 3.12+

The examples assume an Ubuntu/Edubuntu system, but any modern GNOME-based distribution should work.

---

# 1. Clone the Repository

```bash
git clone https://github.com/<your-account>/screen-time-manager.git
cd screen-time-manager
```

---

# 2. Install Python Dependencies

Create a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

---

# 3. Configure the Python Service

Copy the template configuration:

```bash
cp config_template.json config.json
```

Edit `config.json` and configure:

- Home Assistant URL
- REST URL
- Long-Lived Access Token
- monitored users
- Home Assistant entity IDs

Example:

```json
{
    "ha_url": "ws://homeassistant.local:8123/api/websocket",
    "ha_rest_url": "http://homeassistant.local:8123/api",
    "ha_poll_interval": 30,
    "ha_desktop_state_entity": "sensor.desktop_session",

    "token": "YOUR_LONG_LIVED_ACCESS_TOKEN",

    "users": {
        "alice": {
            "active_entity": "...",
            "started_entity": "...",
            "remaining_entity": "..."
        }
    }
}
```

Never commit your real `config.json` to Git.

---

# 4. Install the Python Service

Create a user service:

```bash
mkdir -p ~/.config/systemd/user
```

Create

```
~/.config/systemd/user/screen_time_manager.service
```

Example:

```ini
[Unit]
Description=Screen Time Manager

After=network.target

[Service]
Type=simple

WorkingDirectory=/path/to/screen-time-manager

ExecStart=/path/to/.venv/bin/python /path/to/screen-time-manager/main.py

Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

Reload systemd:

```bash
systemctl --user daemon-reload
```

Enable the service:

```bash
systemctl --user enable screen_time_manager
```

Start it:

```bash
systemctl --user start screen_time_manager
```

Check status:

```bash
systemctl --user status screen_time_manager
```

---

# 5. Install the GNOME Countdown Extension

Copy the extension directory:

```bash
mkdir -p ~/.local/share/gnome-shell/extensions

cp -r \
user/.local/share/gnome-shell/extensions/ha-monitor@local \
~/.local/share/gnome-shell/extensions/
```

Enable it:

```bash
gnome-extensions enable ha-monitor@local
```

Restart GNOME Shell.

- **X11:** `Alt`+`F2`, then `r`
- **Wayland:** log out and back in

The extension should now display the remaining computer time in the top panel.

See **gnome-extension.md** for details.

---

# 6. Install the Focused Window Extension

The Python backend depends on the **Focused Window** GNOME extension to determine which application is currently active.

Install and enable the extension.

See **focused-window-extension.md** for complete instructions.

---

# 7. Install the Home Assistant Package

Copy the provided YAML package into your Home Assistant packages directory.

Example:

```
config/packages/computer_time.yaml
```

Enable packages if necessary:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

Restart Home Assistant.

See **homeassistant.md** for configuration details.

---

# 8. Verify the Installation

When everything is working correctly:

- the systemd service is running
- the countdown appears in the GNOME top panel
- Home Assistant receives a desktop session entity
- Home Assistant updates the remaining computer time
- the desktop countdown follows Home Assistant in real time

---

# Updating

After pulling a newer version:

```bash
git pull
```

Update Python dependencies if necessary:

```bash
pip install -r requirements.txt
```

Restart the user service:

```bash
systemctl --user restart screen_time_manager
```

If the GNOME extension changed, reinstall it and restart GNOME Shell.

---

# Troubleshooting

## Check the service

```bash
systemctl --user status screen_time_manager
```

## View live logs

```bash
journalctl --user -u screen_time_manager -f
```

## Verify the GNOME extension

```bash
gnome-extensions list
```

```bash
gnome-extensions info ha-monitor@local
```

## Verify the Focused Window extension

Run:

```bash
gdbus call \
    --session \
    --dest org.gnome.Shell \
    --object-path /org/gnome/shell/extensions/FocusedWindow \
    --method org.gnome.shell.extensions.FocusedWindow.Get
```

You should receive JSON describing the currently focused window.

---

# Next Steps

After installation, the following documents provide more information:

- **architecture.md** — overall system architecture
- **python.md** — Python backend
- **gnome-extension.md** — countdown panel extension
- **focused-window-extension.md** — Focused Window dependency
- **homeassistant.md** — Home Assistant package
