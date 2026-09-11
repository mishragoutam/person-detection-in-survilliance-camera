import customtkinter as ctk
from pathlib import Path
from storage.database import EventStore
from ui.theme import COLORS, FONTS, PAD
from ui.widgets import ScrollPage, PageHeader, Pill, Card, SecondaryButton, ThirdButton

_ROOT_DIR = Path(__file__).resolve().parent.parent
_EVENT_STORE_PATH = _ROOT_DIR / "events.db"

SEVERITY_COLOR = {"high": COLORS["danger"], "medium": COLORS["warning"], "low": COLORS["success"]}

class EventsPage(ScrollPage):
    """Historical event review backed by SQLite rather than widget state."""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.store = EventStore(_EVENT_STORE_PATH)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", pady=(0, PAD["lg"]))
        PageHeader(header, "Event Operations", "Historical detection events and operator disposition",
                   accent=COLORS["evidence"]).pack(side="left", fill="x", expand=True)
        SecondaryButton(header, "Refresh", command=self.render).pack(side="right")
        ThirdButton(header,"clear", command=self.event_delete).pack(side="right", padx=PAD["sm"])
        self.list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.list_frame.pack(fill="both", expand=True)
        self.render()

    def render(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        events = self.store.list_events(20)
        if not events:
            ctk.CTkLabel(self.list_frame, text="No stored events yet.", font=FONTS["body"],
                         text_color=COLORS["text_muted"]).pack(pady=PAD["xl"])
            return
        for event in events:
            row = Card(self.list_frame)
            row.pack(fill="x", pady=4)
            body = ctk.CTkFrame(row, fg_color="transparent")
            body.pack(fill="x", padx=PAD["md"], pady=PAD["sm"])
            title = f"{event['event_type']}  ·  {event['camera_id']}"
            ctk.CTkLabel(body, text=title, font=FONTS["body_bold"],
                         text_color=COLORS["text_primary"]).pack(side="left")
            Pill(body, event["severity"], SEVERITY_COLOR.get(event["severity"].lower(), COLORS["warning"])).pack(side="left", padx=PAD["sm"])
            ctk.CTkLabel(body, text=f"Score {event['score']}  |  {event['status']}  |  {event['created_at'][:19]}",
                         font=FONTS["small"], text_color=COLORS["text_secondary"]).pack(side="left", padx=PAD["sm"])
            SecondaryButton(body, "Acknowledge", command=lambda e=event: self.acknowledge(e["event_id"])).pack(side="right")
            ThirdButton(body, "Delete", command=lambda e=event: self.event_delete(e["event_id"])).pack(side="right", padx=PAD["sm"])

    def acknowledge(self, event_id):
        self.store.update_status(event_id, "ACKNOWLEDGED")
        self.render()

    def event_delete(self, event_id=None):
        if event_id:
            self.store.delete_event(event_id)
        else:
            self.store.clear_events()
        self.render()
