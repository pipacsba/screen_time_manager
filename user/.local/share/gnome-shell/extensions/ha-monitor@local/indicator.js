import Clutter from 'gi://Clutter';
import St from 'gi://St';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';

export class StatusIndicator {

    constructor() {
        this._createWidgets();
    }

    destroy() {
        if (this._button) {
            this._button.destroy();
            this._button = null;
        }

        this._label = null;
    }

    setStatus(status) {
        const safeStatus = status ?? {
            text: "⏳ Waiting...",
            tooltip: "",
            color: "",
        };

        this._setText(safeStatus.text);
        this._setTooltip(safeStatus.tooltip);
        this._setColor(safeStatus.color);
    }

    _createWidgets() {
        this._button = new PanelMenu.Button(0.0, "HA Monitor");

        this._label = new St.Label({
            text: "Starting...",
            y_align: Clutter.ActorAlign.CENTER,
        });

        this._button.add_child(this._label);

        Main.panel.addToStatusArea(
            "ha-monitor",
            this._button
        );
    }

    _setText(text) {
        if (this._label) {
            this._label.set_text(text ?? "—");
        }
    }

    _setTooltip(tooltip) {
        // There is no native tooltip API in GNOME Shell (St/Clutter). 
        // We will no-op this for now to prevent a TypeError crash.
        // If you need a tooltip, you must manually spawn an St.Label on hover.
    }

    _setColor(color) {
        if (!this._button)
            return;

        // Remove previous state
        this._button.remove_style_class_name("ha-green");
        this._button.remove_style_class_name("ha-yellow");
        this._button.remove_style_class_name("ha-red");

        switch (color) {
            case "green":
                this._button.add_style_class_name("ha-green");
                break;
            case "yellow":
                this._button.add_style_class_name("ha-yellow");
                break;
            case "red":
                this._button.add_style_class_name("ha-red");
                break;
            default:
                break;
        }
    }
}
