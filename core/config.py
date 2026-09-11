import json
import os
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
_CONFIG_PATH = _PROJECT_DIR / "config.json"

_DEFAULT_CONFIG = {
    "telegram": {"bot_token": "", "chat_id": ""},
    "alert_cooldown_seconds": 5,
    "detection": {
        "confidence": 0.40,
        "alert_confirm_frames": 3,
        "capture_width": 960,
        "capture_height": 540
    },
    "distance": {
        "alert_threshold_meters": 5.0,
        "focal_length_px": 700,
        "known_person_height_m": 1.7,
    },
    "cameras": [
        {
            "id": "CAM-01",
            "name": "Main Gate",
            "source": 0,
            "location": {
                "lat": 28.6139,
                "lon": 77.2090,
                "label": "Main Gate - Sector 1",
            },
        }
    ],
}

def load_config() -> dict:
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return _DEFAULT_CONFIG.copy()
    else:
        with open(_CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(_DEFAULT_CONFIG, fh, indent=2)
        return _DEFAULT_CONFIG.copy()

class AppConfig:
    def __init__(self):
        self.raw = load_config()
        self.telegram_token = os.getenv("NETRA_TELEGRAM_BOT_TOKEN", self.raw.get("telegram", {}).get("bot_token", ""))
        self.telegram_chat_id = os.getenv("NETRA_TELEGRAM_CHAT_ID", self.raw.get("telegram", {}).get("chat_id", ""))
        self.alert_cooldown = float(self.raw.get("alert_cooldown_seconds", 5))
        self.cameras = self.raw.get("cameras", _DEFAULT_CONFIG["cameras"])
        
        det_cfg = self.raw.get("detection", {})
        self.detection_conf = float(det_cfg.get("confidence", 0.40))
        self.alert_confirm_frames = max(1, int(det_cfg.get("alert_confirm_frames", 3)))
        self.capture_width = int(det_cfg.get("capture_width", 960))
        self.capture_height = int(det_cfg.get("capture_height", 540))
        
        dist_cfg = self.raw.get("distance", {})
        self.alert_dist_m = float(dist_cfg.get("alert_threshold_meters", 5.0))
        self.focal_length_px = float(dist_cfg.get("focal_length_px", 700))
        self.person_height_m = float(dist_cfg.get("known_person_height_m", 1.7))

    def reload(self):
        self.__init__()

config = AppConfig()
