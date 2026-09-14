import customtkinter as ctk

def apply_theme():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

COLORS = {
    "bg_base":        ("#F4F7FB", "#0B1220"),
    "bg_panel":       ("#FFFFFF", "#111A2C"),
    "bg_panel_alt":   ("#F1F4FA", "#18243A"),
    "bg_sidebar":     ("#FFFFFF", "#0B1220"),
    "sidebar_alt":    ("#17263B", "#1E2F48"),
    "sidebar_text":   ("#F5F8FF", "#F5F8FF"),
    "sidebar_muted":  ("#9FB0C8", "#9FB0C8"),
    "border":         ("#E3E8F2", "#233752"),

    "text_primary":    ("#0B1220", "#FFFFFF"),
    "text_secondary":  ("#5C6C8F", "#A0B1CE"),
    "text_muted":      ("#94A3C4", "#778AAB"),

    "accent_blue":      ("#2F6FE4", "#3D82FF"),
    "accent_blue_hover":("#2558B8", "#2F6FE4"),

    "live":       ("#1FAE74", "#25D38B"),
    "analyze":    ("#128FB0", "#18B8E0"),
    "whitelist":  ("#E07B39", "#FFA25C"),
    "evidence":   ("#D6455B", "#FF5973"),
    "training":   ("#2F6FE4", "#3D82FF"),
    "config":     ("#7351C8", "#9569FF"),

    "success":   ("#1FAE74", "#25D38B"),
    "warning":   ("#E0A72F", "#FFC342"),
    "danger":    ("#D6455B", "#FF5973"),
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

PAD = {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32}
RADIUS = {"sm": 6, "md": 10, "lg": 16}

SIDEBAR_WIDTH = 240
