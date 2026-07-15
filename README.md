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

## 🚀 Installation & Setup[cite: 1]

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
