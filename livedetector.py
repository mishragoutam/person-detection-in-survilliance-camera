"""
livedetector.py — SIH26187 Live Border Surveillance Engine
Features:
  - Real-time YOLOv8 multi-camera detection
  - Accurate distance estimation (pinhole camera model)
  - User-configurable alert distance (config.json)
  - Authorized personnel whitelist (drop photos in authorized/)
  - Virtual border tripwire with color-coded proximity gauge
  - Telegram mobile alerts with snapshot + GPS pin
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
from services.stream_server import StreamServer

STREAM_HOST = os.getenv("NETRA_STREAM_HOST", "127.0.0.1")
STREAM_PORT = int(os.getenv("NETRA_STREAM_PORT", "5001"))

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

    print("=" * 65)
    print("  SIH26187 — Intelligent Video Analytics for Border Surveillance")
    print(f"  Alert Distance : < {config.alert_dist_m} m  (edit config.json)")
    print(f"  Cameras        : {len(cameras)}")
    tg_status = "ACTIVE" if config.telegram_token else "OFF (set bot_token in config.json)"
    print(f"  Telegram       : {tg_status}")
    print("=" * 65)
    print()
    print("  📏 Distance Calibration:")
    print(f"     Current focal_length_px = {config.focal_length_px}")
    print("     Stand 3 m from camera → note bbox height H_px on screen")
    print("     Then: focal_length_px = H_px × 3.0 / 1.7")
    print("=" * 65)

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

    threads = [CameraThread(cam, detector, event_store, evidence_manager, alert_manager) for cam in cameras]
    for t in threads:
        t.start()

    print(f"\n[SYSTEM] Live Video Stream starting on http://{STREAM_HOST}:{STREAM_PORT}/video_feed ...\n")

    def get_frames_callback():
        frames = []
        for t in threads:
            with t.lock:
                f = t.frame
            if f is not None:
                import cv2
                frames.append(cv2.resize(f, (640, 360)))
        return frames

    server = StreamServer(STREAM_HOST, STREAM_PORT, get_frames_callback)
    
    try:
        server.start()
    finally:
        server.stop()
        for thread in threads:
            thread.stop()
        for thread in threads:
            thread.join(timeout=3)
        logger.info("Detector and camera threads stopped")

    print("[SYSTEM] Shutdown complete.")


if __name__ == "__main__":
    main()
