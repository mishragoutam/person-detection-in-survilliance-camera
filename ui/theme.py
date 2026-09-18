import customtkinter as ctk

def apply_theme():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

COLORS = {
    "bg_base":        ("#F0F2F5", "#F0F2F5"),
    "bg_panel":       ("#FFFFFF", "#FFFFFF"),
    "bg_panel_alt":   ("#F9F9F9", "#F9F9F9"),
    "bg_sidebar":     ("#FFFFFF", "#FFFFFF"),
    "sidebar_alt":    ("#F1F1F1", "#F1F1F1"),
    "sidebar_text":   ("#111111", "#111111"),
    "sidebar_muted":  ("#666666", "#666666"),
    "border":         ("#E6E6E6", "#E6E6E6"),

    "text_primary":    ("#111111", "#111111"),
    "text_secondary":  ("#444444", "#444444"),
    "text_muted":      ("#888888", "#888888"),

    "accent_blue":      ("#FF4500", "#FF4500"),  # Changed to VLC orange / Pinterest red
    "accent_blue_hover":("#E03E00", "#E03E00"),

    "live":       ("#E60023", "#E60023"),  # Pinterest red
    "analyze":    ("#444444", "#444444"),
    "whitelist":  ("#FF4500", "#FF4500"),
    "evidence":   ("#111111", "#111111"),
    "training":   ("#FF4500", "#FF4500"),
    "config":     ("#666666", "#666666"),

    "success":   ("#1FAE74", "#1FAE74"),
    "warning":   ("#E0A72F", "#E0A72F"),
    "danger":    ("#E60023", "#E60023"),
}

FONT_FAMILY = "Segoe UI"

FONTS = {
    "display":   (FONT_FAMILY, 26, "bold"),
    "h1":        (FONT_FAMILY, 20, "bold"),
    "h2":        (FONT_FAMILY, 16, "bold"),
    "body":      (FONT_FAMILY, 13),
    "body_bold": (FONT_FAMILY, 13, "bold"),
    "small":     (FONT_FAMILY, 11),
    "small_bold":(FONT_FAMILY, 11, "bold"),
    "mono":      ("Consolas", 12),
}

PAD = {"xs": 8, "sm": 12, "md": 24, "lg": 32, "xl": 48}
RADIUS = {"sm": 24, "md": 16, "lg": 24}

SIDEBAR_WIDTH = 240
