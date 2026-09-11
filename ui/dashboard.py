import json
import datetime
from pathlib import Path
import customtkinter as ctk

from ui.theme import COLORS, FONTS, PAD, RADIUS
from ui.widgets import ScrollPage, PageHeader, Pill, Card, StatTile, PrimaryButton

_ROOT_DIR = Path(__file__).resolve().parent.parent
_ALERTS_DIR = _ROOT_DIR / "alerts"
_AUTH_DIR = _ROOT_DIR / "authorized"
_CONFIG_PATH = _ROOT_DIR / "config.json"

def _get_live_stats():
    alerts_dir = _ALERTS_DIR
    auth_dir = _AUTH_DIR
    alert_count = len(list(alerts_dir.glob("*.jpg"))) if alerts_dir.exists() else 0
    auth_count = 0
    if auth_dir.exists():
        for f in auth_dir.iterdir():
            if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                auth_count += 1
    try:
        with open(_CONFIG_PATH) as f:
            cfg = json.load(f)
        tg = "Connected" if cfg.get("telegram", {}).get("bot_token", "").strip() else "Disconnected"
    except Exception:
        tg = "Unknown"
    return [
        ("Cameras Online", "1", COLORS["live"], ""),
        ("Alerts Today", str(alert_count), COLORS["evidence"], ""),
        ("Personnel Whitelisted", str(auth_count), COLORS["whitelist"], ""),
        ("Telegram", tg, COLORS["training"], ""),
    ]

def _get_recent_alerts(limit=4):
    alerts_dir = _ALERTS_DIR
    if not alerts_dir.exists():
        return []
    files = sorted(alerts_dir.glob("*.jpg"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files[:limit]:
        ts = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%H:%M")
        cam = f.stem.split("_")[0] if "_" in f.stem else "Unknown"
        result.append((ts, f"Camera: {cam}", f"Threat snapshot: {f.name}", "high"))
    return result

SEVERITY_COLOR = {"high": COLORS["danger"], "medium": COLORS["warning"], "low": COLORS["success"]}

class DashboardPage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, PAD["lg"]))
        PageHeader(header_row, "Command Center",
                   "Ministry of Home Affairs — Border Surveillance AI Platform").pack(side="left", fill="x", expand=True)
        Pill(header_row, "ALL SYSTEMS READY", COLORS["success"]).pack(side="right")

        overview = Card(self)
        overview.pack(fill="x", pady=(0, PAD["lg"]))
        overview_inner = ctk.CTkFrame(overview, fg_color="transparent")
        overview_inner.pack(fill="x", padx=PAD["lg"], pady=PAD["md"])
        ctk.CTkFrame(overview_inner, width=5, height=54, fg_color=COLORS["accent_blue"],
                 corner_radius=3).pack(side="left", fill="y", padx=(0, PAD["md"]))
        overview_text = ctk.CTkFrame(overview_inner, fg_color="transparent")
        overview_text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(overview_text, text="Border watch is active",
                 font=FONTS["h2"], text_color=COLORS["text_primary"]).pack(anchor="w")
        ctk.CTkLabel(overview_text,
                 text="Monitor live feeds, review evidence, and keep your response team informed.",
                 font=FONTS["body"], text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(2, 0))
        ctk.CTkLabel(overview_inner, text=datetime.datetime.now().strftime("%A, %d %B %Y"),
                 font=FONTS["small_bold"], text_color=COLORS["text_muted"]).pack(side="right")

        stats_row = ctk.CTkFrame(self, fg_color="transparent")
        stats_row.pack(fill="x", pady=(0, PAD["lg"]))
        self.stat_tiles = []
        for i, (label, value, accent, suffix) in enumerate(_get_live_stats()):
            stats_row.grid_columnconfigure(i, weight=1, uniform="stat")
            tile = StatTile(stats_row, label, value, accent, suffix)
            tile.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else PAD["sm"], 0))
            self.stat_tiles.append(tile)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=2, uniform="body")
        body.grid_columnconfigure(1, weight=1, uniform="body")

        alerts_card = Card(body)
        alerts_card.grid(row=0, column=0, sticky="nsew", padx=(0, PAD["md"]))
        inner = ctk.CTkFrame(alerts_card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=PAD["md"], pady=PAD["md"])
        head = ctk.CTkFrame(inner, fg_color="transparent")
        head.pack(fill="x", pady=(0, PAD["sm"]))
        ctk.CTkLabel(head, text="Recent Alerts", font=FONTS["h2"],
                     text_color=COLORS["text_primary"]).pack(side="left")
        ctk.CTkButton(head, text="View all →", fg_color="transparent",
                      hover_color=COLORS["bg_panel_alt"], text_color=COLORS["accent_blue"],
                      font=FONTS["small_bold"], height=24,
                      command=lambda: self.app.navigate("alerts")).pack(side="right")

        self.alerts_inner = inner
        self._populate_alerts()

        quick_card = Card(body)
        quick_card.grid(row=0, column=1, sticky="nsew")
        qinner = ctk.CTkFrame(quick_card, fg_color="transparent")
        qinner.pack(fill="both", expand=True, padx=PAD["md"], pady=PAD["md"])
        ctk.CTkLabel(qinner, text="Quick Actions", font=FONTS["h2"],
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, PAD["sm"]))

        actions = [
            ("Start Live Surveillance", "cameras", COLORS["live"]),
            ("Analyze a CCTV File", "analyze", COLORS["analyze"]),
            ("Manage Whitelist", "personnel", COLORS["whitelist"]),
            ("Edit Configuration", "settings", COLORS["config"]),
        ]
        for label, target, accent in actions:
            PrimaryButton(qinner, label, accent=accent,
                          command=lambda t=target: self.app.navigate(t)).pack(fill="x", pady=4)
        
        self._update_stats()

    def _populate_alerts(self):
        for widget in self.alerts_inner.winfo_children()[1:]:
            widget.destroy()

        alerts = _get_recent_alerts()
        if not alerts:
            ctk.CTkLabel(self.alerts_inner, text="No alerts today. All clear.", font=FONTS["small"],
                         text_color=COLORS["text_muted"]).pack(pady=PAD["lg"])
        
        for i, (t, loc, desc, sev) in enumerate(alerts):
            row = ctk.CTkFrame(self.alerts_inner, fg_color=COLORS["bg_panel_alt"], corner_radius=RADIUS["sm"])
            row.pack(fill="x", pady=4)
            ctk.CTkFrame(row, width=3, fg_color=SEVERITY_COLOR[sev], corner_radius=2).pack(
                side="left", fill="y", padx=(0, PAD["sm"]), pady=6)
            txt = ctk.CTkFrame(row, fg_color="transparent")
            txt.pack(side="left", fill="x", expand=True, pady=8)
            ctk.CTkLabel(txt, text=f"{loc}", font=FONTS["body_bold"],
                         text_color=COLORS["text_primary"]).pack(anchor="w")
            ctk.CTkLabel(txt, text=desc, font=FONTS["small"],
                         text_color=COLORS["text_secondary"]).pack(anchor="w")
            ctk.CTkLabel(row, text=t, font=FONTS["small"],
                         text_color=COLORS["text_muted"]).pack(side="right", padx=PAD["md"])

    def _update_stats(self):
        stats = _get_live_stats()
        for i, (label, value, accent, suffix) in enumerate(stats):
            if i < len(self.stat_tiles):
                self.stat_tiles[i].val_label.configure(text=value)
        self._populate_alerts()
        self.after(5000, self._update_stats)
