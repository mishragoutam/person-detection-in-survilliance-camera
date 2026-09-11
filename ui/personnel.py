import shutil
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk

from ui.theme import COLORS, FONTS, PAD, RADIUS
from ui.widgets import ScrollPage, PageHeader, Pill, Card, PrimaryButton

_ROOT_DIR = Path(__file__).resolve().parent.parent
_AUTH_DIR = _ROOT_DIR / "authorized"

def _load_authorized_personnel():
    auth_dir = _AUTH_DIR
    auth_dir.mkdir(exist_ok=True)
    people = []
    for i, f in enumerate(sorted(auth_dir.iterdir())):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png"):
            name = f.stem.replace("_", " ").title()
            people.append((f"WL-{i+1:04d}", name, "Whitelisted", "Active", f.name))
    return people


class WhitelistPage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.people = _load_authorized_personnel()

        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, PAD["lg"]))
        PageHeader(header_row, "Authorized Personnel",
                   "Faces in this whitelist are excluded from threat alerts",
                   accent=COLORS["whitelist"]).pack(side="left", fill="x", expand=True)
        PrimaryButton(header_row, "+  Add Person", accent=COLORS["whitelist"],
                      command=self._add_person).pack(side="right")

        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", pady=(0, PAD["md"]))
        self.search_entry = ctk.CTkEntry(
            search_row, placeholder_text="Search by name or ID…", height=36,
            fg_color=COLORS["bg_panel_alt"], border_color=COLORS["border"],
            text_color=COLORS["text_primary"])
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<KeyRelease>", lambda e: self._render_table())

        # Table card
        self.table_card = Card(self)
        self.table_card.pack(fill="both", expand=True)
        self.table_inner = ctk.CTkFrame(self.table_card, fg_color="transparent")
        self.table_inner.pack(fill="both", expand=True, padx=PAD["md"], pady=PAD["md"])

        self._render_table()

    def _render_table(self):
        for w in self.table_inner.winfo_children():
            w.destroy()

        query = self.search_entry.get().lower().strip()

        header = ctk.CTkFrame(self.table_inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, PAD["sm"]))
        for text, w in [("ID", 90), ("Name", 220), ("Role", 180), ("Status", 100), ("", 60)]:
            ctk.CTkLabel(header, text=text, font=FONTS["small_bold"], width=w, anchor="w",
                         text_color=COLORS["text_muted"]).pack(side="left")

        ctk.CTkFrame(self.table_inner, height=1, fg_color=COLORS["border"]).pack(fill="x", pady=(0, PAD["xs"]))

        shown = 0
        for entry in self.people:
            pid, name, role, status = entry[0], entry[1], entry[2], entry[3]
            if query and query not in pid.lower() and query not in name.lower():
                continue
            shown += 1
            row = ctk.CTkFrame(self.table_inner, fg_color=COLORS["bg_panel_alt"] if shown % 2 else "transparent",
                                corner_radius=RADIUS["sm"])
            row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=pid, font=FONTS["mono"], width=90, anchor="w",
                         text_color=COLORS["text_secondary"]).pack(side="left", pady=6)
            ctk.CTkLabel(row, text=name, font=FONTS["body_bold"], width=220, anchor="w",
                         text_color=COLORS["text_primary"]).pack(side="left")
            ctk.CTkLabel(row, text=role, font=FONTS["body"], width=180, anchor="w",
                         text_color=COLORS["text_secondary"]).pack(side="left")
            color = COLORS["success"] if status == "Active" else COLORS["text_muted"]
            Pill(row, status.upper(), color).pack(side="left")
            ctk.CTkButton(row, text="Remove", width=60, height=24, fg_color="transparent",
                          hover_color=COLORS["danger"], text_color=COLORS["danger"],
                          font=FONTS["small"],
                          command=lambda p=pid: self._remove_person(p)).pack(side="right", padx=PAD["sm"])

        if shown == 0:
            ctk.CTkLabel(self.table_inner, text="No matching personnel.", font=FONTS["small"],
                         text_color=COLORS["text_muted"]).pack(pady=PAD["lg"])

    def _add_person(self):
        path = filedialog.askopenfilename(
            title="Select face photo for whitelist",
            filetypes=[("Image files", "*.jpg *.jpeg *.png"), ("All files", "*.*")])
        if path:
            src = Path(path)
            dst = _AUTH_DIR / src.name
            _AUTH_DIR.mkdir(exist_ok=True)
            shutil.copy2(str(src), str(dst))
            self.people = _load_authorized_personnel()
            self._render_table()

    def _remove_person(self, pid):
        # Find the person and delete their file
        for p in self.people:
            if p[0] == pid and len(p) > 4:
                filepath = _AUTH_DIR / p[4]
                if filepath.exists():
                    filepath.unlink()
        self.people = _load_authorized_personnel()
        self._render_table()
