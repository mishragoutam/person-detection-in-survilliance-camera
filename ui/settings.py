import os
import json
from pathlib import Path
import customtkinter as ctk

from ui.theme import COLORS, FONTS, PAD, RADIUS
from ui.widgets import ScrollPage, PageHeader, Card, PrimaryButton, SecondaryButton

_ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = _ROOT_DIR / "config.json"

DEFAULT_CONFIG = {
    "telegram": {
        "bot_token": "",
        "chat_id": "",
        "_help": "Get free bot from @BotFather on Telegram. Leave blank to disable."
    },
    "alert_cooldown_seconds": 15,
    "distance": {
        "alert_threshold_meters": 5.0,
        "_help_threshold": "Alert fires only when person is closer than this distance (meters).",
        "focal_length_px": 700,
        "_help_focal": "Camera focal length in pixels. 700 is typical for 1080p webcam. Increase if distances read too low, decrease if too high.",
        "known_person_height_m": 1.7,
        "_help_height": "Assumed real-world height of a person in meters (used for distance estimation)."
    },
    "cameras": [
        {
            "id": "CAM-01",
            "name": "Main Gate",
            "source": 0,
            "location": {"lat": 28.6139, "lon": 77.2090, "label": "Main Gate - Sector 1"}
        }
    ]
}


def _help_label(master, text):
    return ctk.CTkLabel(master, text=text, font=FONTS["small"], text_color=COLORS["text_muted"],
                         anchor="w", justify="left", wraplength=520)


class ConfigPage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.config = self._load_config()
        self.camera_rows = []

        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, PAD["lg"]))
        PageHeader(header_row, "Edit Config",
                   "Telegram alerts, distance estimation and camera sources",
                   accent=COLORS["config"]).pack(side="left", fill="x", expand=True)
        self.save_status = ctk.CTkLabel(header_row, text="", font=FONTS["small_bold"],
                                         text_color=COLORS["success"])
        self.save_status.pack(side="right")

        # ---------------- Telegram ----------------
        tg = self.config["telegram"]
        tg_card = Card(self)
        tg_card.pack(fill="x", pady=(0, PAD["md"]))
        tinner = ctk.CTkFrame(tg_card, fg_color="transparent")
        tinner.pack(fill="x", padx=PAD["md"], pady=PAD["md"])
        ctk.CTkLabel(tinner, text="Telegram Alerts", font=FONTS["h2"],
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 2))
        _help_label(tinner, tg.get("_help", "")).pack(anchor="w", pady=(0, PAD["sm"]))

        ctk.CTkLabel(tinner, text="Bot Token", font=FONTS["small_bold"],
                     text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.token_entry = ctk.CTkEntry(
            tinner, placeholder_text="123456:ABC-DEF...", height=36, show="•",
            fg_color=COLORS["bg_panel_alt"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"])
        self.token_entry.insert(0, tg.get("bot_token", ""))
        self.token_entry.pack(fill="x", pady=(2, PAD["sm"]))

        ctk.CTkLabel(tinner, text="Chat ID", font=FONTS["small_bold"],
                     text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.chat_entry = ctk.CTkEntry(
            tinner, placeholder_text="-1001234567890", height=36,
            fg_color=COLORS["bg_panel_alt"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"])
        self.chat_entry.insert(0, tg.get("chat_id", ""))
        self.chat_entry.pack(fill="x", pady=(2, 0))

        # ---------------- Alert timing ----------------
        timing_card = Card(self)
        timing_card.pack(fill="x", pady=(0, PAD["md"]))
        ti = ctk.CTkFrame(timing_card, fg_color="transparent")
        ti.pack(fill="x", padx=PAD["md"], pady=PAD["md"])
        ctk.CTkLabel(ti, text="Alert Cooldown", font=FONTS["h2"],
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 2))
        _help_label(ti, "Minimum seconds between repeat alerts for the same event.").pack(
            anchor="w", pady=(0, PAD["sm"]))
        row = ctk.CTkFrame(ti, fg_color="transparent")
        row.pack(fill="x")
        self.cooldown_entry = ctk.CTkEntry(
            row, width=100, height=36, fg_color=COLORS["bg_panel_alt"],
            border_color=COLORS["border"], text_color=COLORS["text_primary"])
        self.cooldown_entry.insert(0, str(self.config.get("alert_cooldown_seconds", 5)))
        self.cooldown_entry.pack(side="left")
        ctk.CTkLabel(row, text="seconds", font=FONTS["body"],
                     text_color=COLORS["text_secondary"]).pack(side="left", padx=(PAD["sm"], 0))

        # ---------------- Distance estimation ----------------
        dist = self.config["distance"]
        dist_card = Card(self)
        dist_card.pack(fill="x", pady=(0, PAD["md"]))
        di = ctk.CTkFrame(dist_card, fg_color="transparent")
        di.pack(fill="x", padx=PAD["md"], pady=PAD["md"])
        ctk.CTkLabel(di, text="Distance Estimation", font=FONTS["h2"],
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, PAD["sm"]))

        ctk.CTkLabel(di, text="Alert Threshold", font=FONTS["small_bold"],
                     text_color=COLORS["text_secondary"]).pack(anchor="w")
        _help_label(di, dist.get("_help_threshold", "")).pack(anchor="w", pady=(0, 4))
        drow = ctk.CTkFrame(di, fg_color="transparent")
        drow.pack(fill="x", pady=(0, PAD["md"]))
        self.dist_value = ctk.CTkLabel(drow, text=f"{dist.get('alert_threshold_meters', 5.0):.1f} m",
                                        font=FONTS["body_bold"], text_color=COLORS["config"], width=60)
        self.dist_value.pack(side="right")
        self.dist_slider = ctk.CTkSlider(
            drow, from_=1, to=20, number_of_steps=38, progress_color=COLORS["config"],
            button_color=COLORS["config"], button_hover_color=COLORS["config"],
            command=lambda v: self.dist_value.configure(text=f"{v:.1f} m"))
        self.dist_slider.set(dist.get("alert_threshold_meters", 5.0))
        self.dist_slider.pack(side="left", fill="x", expand=True, padx=(0, PAD["md"]))

        two_col = ctk.CTkFrame(di, fg_color="transparent")
        two_col.pack(fill="x")
        two_col.grid_columnconfigure(0, weight=1, uniform="c")
        two_col.grid_columnconfigure(1, weight=1, uniform="c")

        left = ctk.CTkFrame(two_col, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, PAD["sm"]))
        ctk.CTkLabel(left, text="Focal Length (px)", font=FONTS["small_bold"],
                     text_color=COLORS["text_secondary"]).pack(anchor="w")
        _help_label(left, dist.get("_help_focal", "")).pack(anchor="w", pady=(0, 4))
        self.focal_entry = ctk.CTkEntry(left, height=36, fg_color=COLORS["bg_panel_alt"],
                                         border_color=COLORS["border"], text_color=COLORS["text_primary"])
        self.focal_entry.insert(0, str(dist.get("focal_length_px", 700)))
        self.focal_entry.pack(fill="x")

        right = ctk.CTkFrame(two_col, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(PAD["sm"], 0))
        ctk.CTkLabel(right, text="Known Person Height (m)", font=FONTS["small_bold"],
                     text_color=COLORS["text_secondary"]).pack(anchor="w")
        _help_label(right, dist.get("_help_height", "")).pack(anchor="w", pady=(0, 4))
        self.height_entry = ctk.CTkEntry(right, height=36, fg_color=COLORS["bg_panel_alt"],
                                          border_color=COLORS["border"], text_color=COLORS["text_primary"])
        self.height_entry.insert(0, str(dist.get("known_person_height_m", 1.7)))
        self.height_entry.pack(fill="x")

        # ---------------- Cameras ----------------
        cam_card = Card(self)
        cam_card.pack(fill="x", pady=(0, PAD["md"]))
        ci = ctk.CTkFrame(cam_card, fg_color="transparent")
        ci.pack(fill="x", padx=PAD["md"], pady=PAD["md"])
        chead = ctk.CTkFrame(ci, fg_color="transparent")
        chead.pack(fill="x", pady=(0, PAD["sm"]))
        ctk.CTkLabel(chead, text="Cameras", font=FONTS["h2"],
                     text_color=COLORS["text_primary"]).pack(side="left")
        SecondaryButton(chead, "+ Add Camera", command=self._add_camera).pack(side="right")

        self.camera_list = ctk.CTkFrame(ci, fg_color="transparent")
        self.camera_list.pack(fill="x")
        for cam in self.config.get("cameras", []):
            self._add_camera(cam)

        # ---------------- Save ----------------
        save_row = ctk.CTkFrame(self, fg_color="transparent")
        save_row.pack(fill="x", pady=(PAD["sm"], 0))
        PrimaryButton(save_row, "Save Configuration", accent=COLORS["config"],
                      command=self._save_config).pack(side="right")

    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                loaded = json.load(f)
                merged = json.loads(json.dumps(DEFAULT_CONFIG))
                merged.update(loaded)
                return merged
        except (FileNotFoundError, json.JSONDecodeError):
            return json.loads(json.dumps(DEFAULT_CONFIG))

    def _add_camera(self, cam=None):
        cam = cam or {"id": f"CAM-{len(self.camera_rows) + 1:02d}", "name": "New Camera",
                       "source": 0, "location": {"lat": 0.0, "lon": 0.0, "label": ""}}
        loc = cam.get("location", {})

        card = ctk.CTkFrame(self.camera_list, fg_color=COLORS["bg_panel_alt"],
                             corner_radius=RADIUS["sm"])
        card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=PAD["sm"], pady=PAD["sm"])

        top = ctk.CTkFrame(inner, fg_color="transparent")
        top.pack(fill="x", pady=(0, PAD["sm"]))

        def field(parent, label, value, width=None):
            col = ctk.CTkFrame(parent, fg_color="transparent")
            ctk.CTkLabel(col, text=label, font=FONTS["small"],
                         text_color=COLORS["text_muted"]).pack(anchor="w")
            e = ctk.CTkEntry(col, height=32, fg_color=COLORS["bg_panel"],
                              border_color=COLORS["border"], text_color=COLORS["text_primary"],
                              width=width or 120)
            e.insert(0, str(value))
            e.pack(anchor="w", fill="x" if width is None else "x")
            return col, e

        row1 = ctk.CTkFrame(inner, fg_color="transparent")
        row1.pack(fill="x", pady=(0, PAD["sm"]))
        c1, id_entry = field(row1, "ID", cam.get("id", ""), 90)
        c1.pack(side="left", padx=(0, PAD["sm"]))
        c2, name_entry = field(row1, "Name", cam.get("name", ""), 180)
        c2.pack(side="left", padx=(0, PAD["sm"]))
        c3, source_entry = field(row1, "Source (index or RTSP URL)", cam.get("source", 0))
        c3.pack(side="left", fill="x", expand=True, padx=(0, PAD["sm"]))
        remove_btn = ctk.CTkButton(row1, text="✕", width=32, height=32, fg_color="transparent",
                                    hover_color=COLORS["danger"], text_color=COLORS["text_secondary"],
                                    command=lambda: self._remove_camera(card))
        remove_btn.pack(side="right")

        row2 = ctk.CTkFrame(inner, fg_color="transparent")
        row2.pack(fill="x")
        c4, lat_entry = field(row2, "Latitude", loc.get("lat", 0.0), 100)
        c4.pack(side="left", padx=(0, PAD["sm"]))
        c5, lon_entry = field(row2, "Longitude", loc.get("lon", 0.0), 100)
        c5.pack(side="left", padx=(0, PAD["sm"]))
        c6, label_entry = field(row2, "Location Label", loc.get("label", ""))
        c6.pack(side="left", fill="x", expand=True)

        self.camera_rows.append({
            "card": card, "id": id_entry, "name": name_entry, "source": source_entry,
            "lat": lat_entry, "lon": lon_entry, "label": label_entry,
        })

    def _remove_camera(self, card):
        self.camera_rows = [r for r in self.camera_rows if r["card"] is not card]
        card.destroy()

    def _parse_source(self, raw):
        raw = raw.strip()
        try:
            return int(raw)
        except ValueError:
            return raw

    def _save_config(self):
        cfg = json.loads(json.dumps(DEFAULT_CONFIG))

        cfg["telegram"]["bot_token"] = self.token_entry.get().strip()
        cfg["telegram"]["chat_id"] = self.chat_entry.get().strip()

        try:
            cfg["alert_cooldown_seconds"] = int(self.cooldown_entry.get().strip())
        except ValueError:
            cfg["alert_cooldown_seconds"] = DEFAULT_CONFIG["alert_cooldown_seconds"]

        cfg["distance"]["alert_threshold_meters"] = round(self.dist_slider.get(), 1)
        try:
            cfg["distance"]["focal_length_px"] = int(self.focal_entry.get().strip())
        except ValueError:
            pass
        try:
            cfg["distance"]["known_person_height_m"] = float(self.height_entry.get().strip())
        except ValueError:
            pass

        cameras = []
        for r in self.camera_rows:
            try:
                lat = float(r["lat"].get().strip())
            except ValueError:
                lat = 0.0
            try:
                lon = float(r["lon"].get().strip())
            except ValueError:
                lon = 0.0
            cameras.append({
                "id": r["id"].get().strip(),
                "name": r["name"].get().strip(),
                "source": self._parse_source(r["source"].get()),
                "location": {"lat": lat, "lon": lon, "label": r["label"].get().strip()},
            })
        cfg["cameras"] = cameras
        self.config = cfg

        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(cfg, f, indent=2)
            self.save_status.configure(text="✓ Saved to config.json", text_color=COLORS["success"])
        except OSError as e:
            self.save_status.configure(text=f"✗ Could not save: {e}", text_color=COLORS["danger"])
        self.after(2500, lambda: self.save_status.configure(text=""))
