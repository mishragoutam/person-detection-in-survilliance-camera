import customtkinter as ctk

from core.system_metrics import collect_metrics
from ui.theme import COLORS, FONTS, PAD
from ui.widgets import ScrollPage, PageHeader

class SystemPage(ScrollPage):
    """Low-overhead runtime health view."""

    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.metrics = ctk.CTkTextbox(self, height=300, fg_color=COLORS["bg_panel"],
                                      text_color=COLORS["text_primary"], font=FONTS["mono"])
        PageHeader(self, "System Health", "Runtime, process, and accelerator telemetry",
                   accent=COLORS["config"]).pack(fill="x", pady=(0, PAD["lg"]))
        self.metrics.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self):
        values = collect_metrics()
        self.metrics.configure(state="normal")
        self.metrics.delete("1.0", "end")
        self.metrics.insert("end", "NETRA SYSTEM STATUS\n\n")
        for key, value in values.items():
            self.metrics.insert("end", f"{key.replace('_', ' ').title():20} {value}\n")
        self.metrics.configure(state="disabled")
        self.after(3000, self.refresh)
