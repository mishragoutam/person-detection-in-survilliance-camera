import customtkinter as ctk
from ui.theme import COLORS, FONTS, PAD, RADIUS
from ui.widgets import Card, PrimaryButton

class LoginPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=COLORS["bg_base"])
        self.app = app

        # Center everything
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        card = Card(self)
        card.grid(row=1, column=1, sticky="nsew")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=PAD["xl"], pady=PAD["xl"], fill="both", expand=True)

        ctk.CTkLabel(inner, text="NETRA Login", font=FONTS["display"],
                     text_color=COLORS["text_primary"]).pack(pady=(0, PAD["lg"]))

        # Username
        ctk.CTkLabel(inner, text="Username", font=FONTS["small_bold"],
                     text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 2))
        self.username_entry = ctk.CTkEntry(inner, font=FONTS["body"], height=38,
                                           corner_radius=RADIUS["sm"], border_color=COLORS["border"],
                                           fg_color=COLORS["bg_panel_alt"])
        self.username_entry.pack(fill="x", pady=(0, PAD["md"]))

        # Password
        ctk.CTkLabel(inner, text="Password", font=FONTS["small_bold"],
                     text_color=COLORS["text_secondary"]).pack(anchor="w", pady=(0, 2))
        self.password_entry = ctk.CTkEntry(inner, font=FONTS["body"], height=38,
                                           corner_radius=RADIUS["sm"], border_color=COLORS["border"],
                                           fg_color=COLORS["bg_panel_alt"], show="*")
        self.password_entry.pack(fill="x", pady=(0, PAD["lg"]))

        self.error_label = ctk.CTkLabel(inner, text="", font=FONTS["small"], text_color=COLORS["danger"])
        self.error_label.pack(pady=(0, PAD["sm"]))

        PrimaryButton(inner, "Sign In", command=self.attempt_login).pack(fill="x")

        # Allow pressing Enter to login
        self.password_entry.bind("<Return>", lambda e: self.attempt_login())
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())

    def attempt_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self.error_label.configure(text="Please enter both username and password")
            return

        role = None
        if hasattr(self.app, 'event_store'):
            role = self.app.event_store.authenticate_user(username, password)
        
        if role:
            self.error_label.configure(text="")
            self.app.current_user = {"username": username, "role": role}
            self.app.event_store.log_login(username, role)
            
            # Start timer if needed, handled in app
            if hasattr(self.app, 'on_login_success'):
                self.app.on_login_success()
            else:
                self.app.sidebar.update_visibility()
                self.app.navigate("dashboard")
        else:
            self.error_label.configure(text="Invalid credentials")
