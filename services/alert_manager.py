import time
import threading
import logging
from typing import List

from core.config import config

logger = logging.getLogger("netra.alert_manager")


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

    def dispatch_alert(
        self,
        camera: dict,
        snapshot_path: str,
        labels: List[str],
        distances: List[float],
    ) -> None:
        """Dispatch Web Push alert notification asynchronously."""
        # Build a public URL for the snapshot so the mobile app can fetch it.
        # The snapshot is served by api_server.py at /api/snapshot/<event_id>
        # We pass the file path; push_service will use snapshot_url if provided.
        threading.Thread(
            target=self._push_worker,
            args=(camera, labels, distances, snapshot_path),
            daemon=True,
        ).start()

    @staticmethod
    def _push_worker(
        camera: dict,
        labels: List[str],
        distances: List[float],
        snapshot_path: str,
    ) -> None:
        try:
            from services.push_service import send_alert_notification
            sent = send_alert_notification(
                camera=camera,
                labels=labels,
                distances=distances,
                snapshot_url=None,  # URL resolved client-side via events API
            )
            logger.info("Web Push sent to %d subscriber(s) for %s", sent, camera.get("id"))
        except Exception as exc:
            logger.warning("Web Push dispatch failed: %s", exc)
