import customtkinter as ctk
from ui.theme import COLORS, FONTS, PAD, RADIUS
from ui.widgets import ScrollPage, PageHeader, Card

class LoginRecordsPage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app

        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, PAD["lg"]))
        PageHeader(header_row, "Login Records",
                   "Audit log of personnel system access").pack(side="left", fill="x", expand=True)

        self.records_container = ctk.CTkFrame(self, fg_color="transparent")
        self.records_container.pack(fill="both", expand=True)

        self.refresh_records()

    def refresh_records(self):
        for child in self.records_container.winfo_children():
            child.destroy()

        if hasattr(self.app, 'event_store'):
            records = self.app.event_store.get_login_records(limit=50)
        else:
            records = []

        if not records:
            ctk.CTkLabel(self.records_container, text="No login records found.", font=FONTS["body"], text_color=COLORS["text_muted"]).pack(pady=PAD["lg"])
            return

        # Header
        header_card = Card(self.records_container, fg_color=COLORS["bg_panel_alt"])
        header_card.pack(fill="x", pady=(0, PAD["sm"]))
        inner_h = ctk.CTkFrame(header_card, fg_color="transparent")
        inner_h.pack(fill="x", padx=PAD["md"], pady=PAD["sm"])
        
        inner_h.grid_columnconfigure(0, weight=2)
        inner_h.grid_columnconfigure(1, weight=1)
        inner_h.grid_columnconfigure(2, weight=2)
        
        ctk.CTkLabel(inner_h, text="USERNAME", font=FONTS["small_bold"], text_color=COLORS["text_muted"]).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(inner_h, text="ROLE", font=FONTS["small_bold"], text_color=COLORS["text_muted"]).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(inner_h, text="LOGIN TIME", font=FONTS["small_bold"], text_color=COLORS["text_muted"]).grid(row=0, column=2, sticky="w")

        # Rows
        for rec in records:
            row_card = Card(self.records_container)
            row_card.pack(fill="x", pady=2)
            
            inner = ctk.CTkFrame(row_card, fg_color="transparent")
            inner.pack(fill="x", padx=PAD["md"], pady=PAD["sm"])
            
            inner.grid_columnconfigure(0, weight=2)
            inner.grid_columnconfigure(1, weight=1)
            inner.grid_columnconfigure(2, weight=2)
            
            ctk.CTkLabel(inner, text=rec.get("username", "Unknown"), font=FONTS["body_bold"], text_color=COLORS["text_primary"]).grid(row=0, column=0, sticky="w")
            
            role_text = rec.get("role", "Unknown").upper()
            role_color = COLORS["success"] if role_text == "ADMIN" else COLORS["training"]
            ctk.CTkLabel(inner, text=role_text, font=FONTS["small_bold"], text_color=role_color).grid(row=0, column=1, sticky="w")
            
            time_text = rec.get("login_time", "").replace("T", " ")[:19]
            ctk.CTkLabel(inner, text=time_text, font=FONTS["mono"], text_color=COLORS["text_secondary"]).grid(row=0, column=2, sticky="w")
