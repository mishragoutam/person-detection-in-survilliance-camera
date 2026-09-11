import customtkinter as ctk

def apply_theme():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

COLORS = {
    "bg_base":        "#F4F7FB",   # app background (soft white)
    "bg_panel":       "#FFFFFF",   # cards / panels
    "bg_panel_alt":   "#F1F4FA",   # nested panels / inputs
    "bg_sidebar":     "#FFFFFF",   # sidebar background
    "sidebar_alt":    "#17263B",   # active / hover sidebar surface
    "sidebar_text":   "#F5F8FF",
    "sidebar_muted":  "#9FB0C8",
    "border":         "#E3E8F2",   # subtle borders / dividers

    "text_primary":    "#0B1220",  # matches logo navy
    "text_secondary":  "#5C6C8F",
    "text_muted":      "#94A3C4",

    "accent_blue":      "#2F6FE4",  # logo blue (triangle)
    "accent_blue_hover":"#2558B8",

    # module accents
    "live":       "#1FAE74",   # green  — Live Camera Surveillance
    "analyze":    "#128FB0",   # teal   — Analyze CCTV Video File
    "whitelist":  "#E07B39",   # orange — Authorized Personnel (logo orange)
    "evidence":   "#D6455B",   # rose   — Threat Evidence
    "training":   "#2F6FE4",   # blue   — AI Training Graphs
    "config":     "#7351C8",   # violet — Edit Config

    "success":   "#1FAE74",
    "warning":   "#E0A72F",
    "danger":    "#D6455B",
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
