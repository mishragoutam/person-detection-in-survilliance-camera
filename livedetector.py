"""
livedetector.py — SIH26187 Live Border Surveillance Engine
Features:
  - Real-time YOLOv8 multi-camera detection
  - Accurate distance estimation (pinhole camera model)
  - User-configurable alert distance (config.json)
  - Authorized personnel whitelist (drop photos in authorized/)
  - Virtual border tripwire with color-coded proximity gauge
  - Web Push mobile alerts with snapshot (replaces Telegram)
  - REST API for mobile app (alerts, events, recordings)
  - Cloudflare Zero Trust tunnel compatible
  - Auto event recording on threat detection
"""

import os
import argparse
import logging
from pathlib import Path

# Setup logging before importing other modules
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("netra.detector")

os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")

from core.config import config
from core.personnel import load_authorized_faces
from core.detector import Detector
from core.camera_manager import CameraThread
from storage.database import EventStore
from services.evidence import EvidenceManager
from services.alert_manager import AlertManager
from api_server import ApiServer, update_frame
from services.push_service import get_public_vapid_key, generate_vapid_keys

API_HOST = os.getenv("NETRA_API_HOST", "0.0.0.0")   # 0.0.0.0 so CF tunnel can reach it
API_PORT = int(os.getenv("NETRA_API_PORT", "5001"))


def _ensure_vapid_keys() -> None:
    """Generate VAPID keys on first run if they don't exist."""
    key = get_public_vapid_key()
    if not key:
        logger.info("Generating VAPID keys for Web Push (first run)...")
        generate_vapid_keys()
        key = get_public_vapid_key()
        if key:
            logger.info("VAPID keys ready. Public key: %s...", key[:20])
        else:
            logger.warning("VAPID key generation failed. Push notifications may not work.")
    else:
        logger.info("VAPID keys loaded. Public key: %s...", key[:20])


def main() -> None:
    parser = argparse.ArgumentParser(description="NETRA live border surveillance detector")
    parser.add_argument("--camera-id", help="Run only the configured camera with this ID")
    args = parser.parse_args()

    cameras = config.cameras
    if args.camera_id:
        cameras = [camera for camera in cameras if str(camera.get("id")) == args.camera_id]
        if not cameras:
            logger.error("Camera ID %s was not found in config.json", args.camera_id)
            return

    _ensure_vapid_keys()

    print("=" * 70)
    print("  SIH26187 — Intelligent Video Analytics for Border Surveillance")
    print(f"  Alert Distance : < {config.alert_dist_m} m  (edit config.json)")
    print(f"  Cameras        : {len(cameras)}")
    print(f"  API / Stream   : http://{API_HOST}:{API_PORT}")
    print(f"  Live Feed      : http://localhost:{API_PORT}/video_feed")
    print(f"  Alerts API     : http://localhost:{API_PORT}/api/alerts")
    print(f"  Notifications  : Web Push (mobile app)")
    print("=" * 70)
    print()

    load_authorized_faces()

    project_dir = Path(__file__).resolve().parent
    event_store = EventStore(project_dir / "events.db")
    evidence_manager = EvidenceManager(project_dir / "evidence")
    alert_manager = AlertManager()

    # Load Detector
    detector = Detector(config.detection_conf)
    if not detector.models:
        logger.error("No models loaded. Exiting.")
        return

    threads = [
        CameraThread(cam, detector, event_store, evidence_manager, alert_manager)
        for cam in cameras
    ]

    # Patch each CameraThread to also push frames to the API server's frame store
    _original_runs = {}
    for t in threads:
        cam_id = t.cam_id
        original_run = t.run

        def _patched_run(thread=t, cid=cam_id):
            """Run the camera thread and stream frames to the API."""
            import threading as _threading
            stop = _threading.Event()

            def _frame_pusher():
                while not stop.is_set():
                    import time
                    with thread.lock:
                        frame = thread.frame
                    if frame is not None:
                        update_frame(cid, frame)
                    time.sleep(0.04)

            pusher = _threading.Thread(target=_frame_pusher, daemon=True)
            pusher.start()
            try:
                original_run()
            finally:
                stop.set()

        t.run = _patched_run

    for t in threads:
        t.start()

    # Start REST API + stream server
    api_server = ApiServer(API_HOST, API_PORT, event_store)
    api_server.start()

    logger.info("NETRA running. Connect mobile app to this machine's API.")
    logger.info("Tip: use 'cloudflared tunnel --url http://localhost:%s' to expose.", API_PORT)

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        logger.info("Shutdown requested (Ctrl+C)")
    finally:
        api_server.stop()
        for thread in threads:
            thread.stop()
        for thread in threads:
            thread.join(timeout=3)
        logger.info("Detector and camera threads stopped")

    print("[SYSTEM] Shutdown complete.")


if __name__ == "__main__":
    main()
