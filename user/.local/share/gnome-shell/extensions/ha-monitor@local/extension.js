import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';
import { StatusIndicator } from './indicator.js';

// Promisify Gio.File async methods so they can be used with async/await
Gio._promisify(
    Gio.File.prototype,
    'load_contents_async',
    'load_contents_finish'
);

export default class HaMonitorExtension extends Extension {

    enable() {
        this._indicator = new StatusIndicator();
        this._file = this._statusFile();
        this._monitor = null;

        this._cancellable = new Gio.Cancellable();
        this._loadToken = 0;

        this._setupMonitor();

        // Initial load
        this._loadStatusAsync().catch(console.error);
    }

    disable() {
        // Cancel async IO natively
        if (this._cancellable) {
            this._cancellable.cancel();
            this._cancellable = null;
        }

        this._loadToken++; // Invalidate any JavaScript callbacks still waiting

        // Stop file monitor
        if (this._monitor) {
            this._monitor.cancel();
            this._monitor = null;
        }

        this._file = null;

        // Destroy UI safely
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }

    _statusFile() {
        return Gio.File.new_for_path(
            GLib.build_filenamev([
                GLib.get_user_runtime_dir(),
                "ha-time",
                "status.json",
            ])
        );
    }

    async _loadStatusAsync() {
        const myToken = ++this._loadToken;

        try {
            const [bytes] = await this._file.load_contents_async(this._cancellable);

            if (myToken !== this._loadToken || !this._indicator)
                return;

            const text = new TextDecoder().decode(bytes);

            const json = JSON.parse(text);

            this._indicator.setStatus({
                text: json.text ?? "—",
                tooltip: json.tooltip ?? "",
                color: json.color ?? "",
            });

        } catch (e) {
            if (myToken !== this._loadToken || !this._indicator)
                return;

            if (e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.CANCELLED))
                return;

            if (!e.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.NOT_FOUND)) {
                console.error(`[HA Monitor] Failed to read status: ${e.message}`);
            }

            this._indicator.setStatus({
                text: "⏳ Waiting...",
                tooltip: "Waiting for status file",
                color: ""
            });
        }
    }

    _setupMonitor() {
        try {
            this._monitor = this._file.monitor_file(
                Gio.FileMonitorFlags.NONE,
                null
            );

            this._monitor.connect(
                "changed",
                (_monitor, _file, _otherFile, eventType) => {
                    if (eventType === Gio.FileMonitorEvent.CHANGES_DONE_HINT) {
                        this._loadStatusAsync().catch(console.error);
                    }
                }
            );

        } catch (e) {
            console.error(`[HA Monitor] FileMonitor failed: ${e.message}`);
        }
    }
}
