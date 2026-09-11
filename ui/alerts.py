import datetime
from pathlib import Path
from PIL import Image

import customtkinter as ctk
from ui.theme import COLORS, FONTS, PAD, RADIUS
from ui.widgets import ScrollPage, PageHeader, Pill, Card, SecondaryButton

_ROOT_DIR = Path(__file__).resolve().parent.parent
_ALERTS_DIR = _ROOT_DIR / "alerts"

def _load_evidence():
    alerts_dir = _ALERTS_DIR
    if not alerts_dir.exists():
        return []
    files = sorted(alerts_dir.glob("*.jpg"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files:
        cam = f.stem.split("_")[0] if "_" in f.stem else "Unknown"
        ts = datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime("%b %d, %H:%M")
        result.append((f"Camera: {cam}", ts, f"Threat: {f.name}", "high", f.name))
    return result

SEVERITY_COLOR = {"high": COLORS["danger"], "medium": COLORS["warning"], "low": COLORS["success"]}

class EvidencePage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, PAD["md"]))
        PageHeader(header_row, "Threat Evidence & Snapshots",
                   "Captured frames from alerts/ — most recent first",
                   accent=COLORS["evidence"]).pack(side="left", fill="x", expand=True)

        filter_row = ctk.CTkFrame(self, fg_color="transparent")
        filter_row.pack(fill="x", pady=(0, PAD["lg"]))
        self.filter_var = ctk.StringVar(value="All")
        for label in ["All", "High", "Medium", "Low"]:
            SecondaryButton(filter_row, label, command=lambda l=label: self._set_filter(l)).pack(
                side="left", padx=(0, PAD["sm"]))

        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="both", expand=True)
        for c in range(3):
            self.grid_frame.grid_columnconfigure(c, weight=1, uniform="grid")

        self._render_grid()

    def _set_filter(self, label):
        self.filter_var.set(label)
        self._render_grid()

    def _render_grid(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()

        filt = self.filter_var.get().lower()
        all_items = _load_evidence()
        items = [e for e in all_items if filt == "all" or e[3] == filt]

        for i, item in enumerate(items):
            camera, ts, desc, sev = item[0], item[1], item[2], item[3]
            card = Card(self.grid_frame)
            card.grid(row=i // 3, column=i % 3, sticky="nsew", padx=PAD["sm"], pady=PAD["sm"])

            thumb = ctk.CTkFrame(card, height=140, fg_color=COLORS["bg_base"],
                                  corner_radius=RADIUS["sm"])
            thumb.pack(fill="x", padx=PAD["sm"], pady=(PAD["sm"], 0))
            
            if len(item) > 4:
                img_path = _ALERTS_DIR / item[4]
                if img_path.exists():
                    try:
                        pil = Image.open(str(img_path)).resize((280, 140), Image.LANCZOS)
                        ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(280, 140))
                        ctk.CTkLabel(thumb, image=ctk_img, text="").place(relx=0.5, rely=0.5, anchor="center")
                    except Exception:
                        ctk.CTkLabel(thumb, text="🖼 snapshot", font=FONTS["small"],
                                     text_color=COLORS["text_muted"]).place(relx=0.5, rely=0.5, anchor="center")
                else:
                    ctk.CTkLabel(thumb, text="🖼 snapshot", font=FONTS["small"],
                                 text_color=COLORS["text_muted"]).place(relx=0.5, rely=0.5, anchor="center")
            else:
                ctk.CTkLabel(thumb, text="🖼 snapshot", font=FONTS["small"],
                             text_color=COLORS["text_muted"]).place(relx=0.5, rely=0.5, anchor="center")

            body = ctk.CTkFrame(card, fg_color="transparent")
            body.pack(fill="x", padx=PAD["sm"], pady=PAD["sm"])
            top = ctk.CTkFrame(body, fg_color="transparent")
            top.pack(fill="x")
            ctk.CTkLabel(top, text=camera, font=FONTS["body_bold"],
                         text_color=COLORS["text_primary"], anchor="w").pack(side="left", fill="x", expand=True)
            Pill(top, sev.upper(), SEVERITY_COLOR[sev]).pack(side="right")
            ctk.CTkLabel(body, text=desc, font=FONTS["small"],
                         text_color=COLORS["text_secondary"], anchor="w").pack(fill="x", pady=(2, 0))
            ctk.CTkLabel(body, text=ts, font=FONTS["small"],
                         text_color=COLORS["text_muted"], anchor="w").pack(fill="x")

        if not items:
            ctk.CTkLabel(self.grid_frame, text="No evidence matches this filter.",
                         font=FONTS["small"], text_color=COLORS["text_muted"]).grid(
                row=0, column=0, columnspan=3, pady=PAD["lg"])
