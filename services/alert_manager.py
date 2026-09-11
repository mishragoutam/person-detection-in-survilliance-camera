import time
import threading
from typing import List, Optional
from services.telegram import send_telegram_alert
from core.config import config

class AlertManager:
    def __init__(self):
        self.last_alert_time_per_camera = {}

    def can_dispatch(self, camera: dict, force: bool = False) -> bool:
        """Check if alert cooldown has passed."""
        cam_id = camera.get("id", "unknown")
        now = time.time()
        last_time = self.last_alert_time_per_camera.get(cam_id, 0.0)

        if not force and (now - last_time < config.alert_cooldown):
            return False

        self.last_alert_time_per_camera[cam_id] = now
        return True

    def dispatch_alert(self, 
                       camera: dict, 
                       snapshot_path: str, 
                       labels: List[str], 
                       distances: List[float]) -> None:
        """Dispatch Telegram alert asynchronously."""
        if config.telegram_token and config.telegram_chat_id:
            threading.Thread(
                target=send_telegram_alert,
                args=(config.telegram_token, config.telegram_chat_id, snapshot_path, camera, labels, distances),
                daemon=True,
            ).start()
