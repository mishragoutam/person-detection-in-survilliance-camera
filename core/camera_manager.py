import time
import threading
import datetime
import cv2
import numpy as np
import logging
from pathlib import Path

from core.config import config
from core.tracker import DistanceTracker, get_distance_color
from core.personnel import is_authorized
from core.threat_engine import ThreatEngine
from storage.database import EventStore
from services.evidence import EvidenceManager
from services.alert_manager import AlertManager
from core.detector import Detector
from core.motion_detector import CameraMotionDetector

logger = logging.getLogger("netra.camera_manager")

class CameraThread(threading.Thread):
    def __init__(self, camera_cfg: dict, detector: Detector, event_store: EventStore, evidence_manager: EvidenceManager, alert_manager: AlertManager):
        super().__init__(daemon=True)
        self.cfg = camera_cfg
        self.cam_id = str(self.cfg.get("id", "CAM-01"))
        self.cam_name = str(self.cfg.get("name", "Camera"))
        self.source = self.cfg.get("source", 0)
        self.loc = self.cfg.get("location", {})
        
        self.detector = detector
        self.event_store = event_store
        self.evidence_manager = evidence_manager
        self.alert_manager = alert_manager
        self.threat_engine = ThreatEngine(config.alert_dist_m)
        self.dist_tracker = DistanceTracker()
        self.motion_detector = CameraMotionDetector()
        self.dynamic_focal_scale = 1.0
        
        self.fps = 0.0
        self._fc = 0
        self._ft = time.time()
        
        self.frame = None
        self.lock = threading.Lock()
        self.writer = None
        self.recording = False
        self.rec_start = 0.0
        self.threat_streak = 0
        self.last_threat_time = 0.0
        self.last_recal_time = time.time()
        self.show_recal_msg_until = 0.0
        
        self.stop_event = threading.Event()
        self._capture_lock = threading.Lock()
        self._latest_frame = None
        self._frame_number = 0
        self._capture_thread = None

    def _open_capture(self, src):
        cap = cv2.VideoCapture(src, cv2.CAP_DSHOW) if isinstance(src, int) else cv2.VideoCapture(src)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(src)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        if cap.isOpened():
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.capture_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.capture_height)
        return cap

    def _capture_loop(self, src):
        cap = self._open_capture(src)
        while not self.stop_event.is_set():
            if not cap.isOpened():
                time.sleep(0.2)
                cap.release()
                cap = self._open_capture(src)
                continue
            ret, frame = cap.read()
            if not ret:
                cap.release()
                cap = self._open_capture(src)
                time.sleep(0.05)
                continue
            with self._capture_lock:
                self._latest_frame = frame
                self._frame_number += 1
        cap.release()

    def stop(self):
        self.stop_event.set()

    def run(self):
        src = self.source
        if isinstance(src, (float,)):
            src = int(src)
        if isinstance(src, str) and src.isdigit():
            src = int(src)

        self._capture_thread = threading.Thread(target=self._capture_loop, args=(src,), daemon=True)
        self._capture_thread.start()
        
        processed_frame_number = -1
        
        logger.info("%s %s | dual-model detection | alert < %s m", self.cam_id, self.cam_name, config.alert_dist_m)

        while not self.stop_event.is_set():
            with self._capture_lock:
                frame_number = self._frame_number
                frame = None if self._latest_frame is None else self._latest_frame.copy()
            if frame is None or frame_number == processed_frame_number:
                time.sleep(0.005)
                continue
            processed_frame_number = frame_number
            H, W = frame.shape[:2]

            box_data = self.detector.detect(frame)
            threat = False
            t_labels = []
            t_dists = []
            all_dists = []
            
            # Detect camera movement (PTZ)
            has_moved, zoom_scale = self.motion_detector.detect_motion(frame)
            
            now_time = time.time()
            if now_time - self.last_recal_time >= 20.0:
                self.dist_tracker.reset()
                self.last_recal_time = now_time
                self.show_recal_msg_until = now_time + 2.0

            if has_moved:
                logger.debug("[%s] Camera pan/tilt detected. Recalibrating tracking buffers.", self.cam_id)
                self.dist_tracker.reset()
                self.show_recal_msg_until = now_time + 2.0
                
            if abs(zoom_scale - 1.0) > 0.01:
                # Adjust focal scale dynamically
                self.dynamic_focal_scale *= zoom_scale
                # Clamp to prevent runaway scaling in case of errors
                self.dynamic_focal_scale = max(0.2, min(5.0, self.dynamic_focal_scale))

            detections_for_tracker = [
                (x1, y1, x2, y2, bbox_h, cls_id)
                for cls_id, conf, name, x1, y1, x2, y2, bbox_h in box_data
            ]

            smoothed_results = self.dist_tracker.update(detections_for_tracker, focal_scale=self.dynamic_focal_scale)

            for (tid, dist_m), (cls_id, conf, name, x1, y1, x2, y2, bbox_h) in zip(smoothed_results, box_data):
                all_dists.append(dist_m)
                dcolor = get_distance_color(dist_m)

                is_auth, auth_name = False, ""
                if cls_id == 1:
                    head_y2 = max(0, y1 + int(bbox_h * 0.40))
                    head_crop = frame[max(0, y1) : head_y2, max(0, x1) : min(W, x2)]
                    is_auth, auth_name = is_authorized(head_crop)

                close = dist_m <= config.alert_dist_m
                if close and cls_id == 1 and not is_auth:
                    threat = True
                    dcolor = (0, 0, 255)
                    t_labels.append(name)
                    t_dists.append(dist_m)

                box_color = (255, 0, 0) if is_auth else dcolor
                cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)

                lbl = f"✓ {auth_name} | {dist_m} m" if is_auth else f"[#{tid}] {name} {conf:.0%} | {dist_m} m"
                (lw, lh), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 2)
                cv2.rectangle(frame, (x1, y1 - lh - 8), (x1 + lw + 6, y1), box_color, -1)
                cv2.putText(frame, lbl, (x1 + 3, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2)

                ratio = max(0.0, min(1.0, 1.0 - dist_m / (config.alert_dist_m * 2)))
                bar_h = int(bbox_h * ratio)
                cv2.rectangle(frame, (x2 + 3, y1), (x2 + 10, y2), (40, 40, 40), -1)
                cv2.rectangle(frame, (x2 + 3, y2 - bar_h), (x2 + 10, y2), dcolor, -1)

            if threat:
                self.threat_streak += 1
            else:
                self.threat_streak = 0
            
            confirmed_threat = self.threat_streak >= config.alert_confirm_frames
            threat = confirmed_threat

            if threat:
                cv2.rectangle(frame, (0, 0), (W, 100), (0, 0, 160), -1)
                cv2.putText(frame, "⚠  THREAT DETECTED — BORDER BREACH  ⚠", (W // 2 - 310, 65), cv2.FONT_HERSHEY_SIMPLEX, 1.05, (255, 255, 255), 3)

                now = time.time()
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                snap = f"alerts/{self.cam_id}_{ts}.jpg"
                
                if self.alert_manager.can_dispatch(self.cfg, force=False):
                    self.last_threat_time = now
                    if not cv2.imwrite(snap, frame):
                        logger.error("Failed to write evidence snapshot: %s", snap)
                    else:
                        self.alert_manager.dispatch_alert(self.cfg, snap, t_labels, t_dists)
                        assessment = self.threat_engine.assess(
                            is_person=True, authorized=False,
                            confidence=max((float(item[1]) for item in box_data if item[0] == 1), default=0.0),
                            distance_m=min(t_dists) if t_dists else None,
                        )
                        event_id = self.event_store.add_event({
                            "camera_id": self.cam_id,
                            "location": self.loc.get("label", self.cam_name),
                            "event_type": assessment.event_type,
                            "severity": assessment.severity,
                            "score": assessment.score,
                            "confidence": max((float(item[1]) for item in box_data if item[0] == 1), default=0.0),
                            "distance_m": min(t_dists) if t_dists else None,
                            "evidence_path": snap,
                            "metadata": {"labels": t_labels, "distances": t_dists},
                        })
                        evidence_dir = self.evidence_manager.event_directory(event_id)
                        self.evidence_manager.write_metadata({
                            "event_id": event_id,
                            "camera_id": self.cam_id,
                            "snapshot": snap,
                            "severity": assessment.severity,
                            "score": assessment.score,
                        }, evidence_dir)
                        logger.warning("ALERT camera=%s distances=%s evidence=%s", self.cam_id, t_dists, snap)

                if threat and not self.recording:
                    rec = f"alerts/{self.cam_id}_{ts}.avi"
                    fourcc = cv2.VideoWriter_fourcc(*"XVID")
                    frame_h, frame_w = frame.shape[:2]
                    self.writer = cv2.VideoWriter(rec, fourcc, 20.0, (frame_w, frame_h))
                    if self.writer.isOpened():
                        self.recording = True
                        self.rec_start = now
                        self.last_threat_time = now
                    else:
                        logger.error("[%s] ❌ Failed to start video recording.", self.cam_id)

            if self.recording and time.time() - self.last_threat_time > 15:
                self.recording = False
                if self.writer is not None:
                    self.writer.release()
                    self.writer = None
                logger.info("[%s] Recording saved to alerts/", self.cam_id)

            if self.recording and self.writer is not None:
                self.writer.write(frame)

            self._fc += 1
            elapsed = time.time() - self._ft
            if elapsed >= 0.5:
                self.fps = self._fc / elapsed
                self._fc = 0
                self._ft = time.time()

            lat = float(self.loc.get("lat", 0.0))
            lon = float(self.loc.get("lon", 0.0))
            loc_lbl = str(self.loc.get("label", self.cam_name))
            ts_str = datetime.datetime.now().strftime("%H:%M:%S  %d-%b-%Y")

            if not threat:
                cv2.putText(frame, f"{self.cam_id} | {self.cam_name}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
            cv2.putText(frame, f"FPS:{self.fps:.1f}  Objects:{len(box_data)}", (12, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(frame, f"GPS:{lat:.4f},{lon:.4f}  {loc_lbl}", (12, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 0), 1)
            
            y_off = 135
            for i, d in enumerate(all_dists):
                cv2.putText(frame, f"Target {i+1} Dist: {d}m", (12, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                y_off += 20
                
            tw, _ = cv2.getTextSize(ts_str, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)[0]
            cv2.putText(frame, ts_str, (W - tw - 10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 255), 1)
            
            if time.time() < self.show_recal_msg_until:
                rw, _ = cv2.getTextSize("RECALIBRATING DISTANCE...", cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
                cv2.putText(frame, "RECALIBRATING DISTANCE...", ((W - rw) // 2, H - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            
            if self.recording:
                rl = f"● REC {int(time.time() - self.rec_start)}s"
                rw, _ = cv2.getTextSize(rl, cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2)[0]
                cv2.putText(frame, rl, ((W - rw) // 2, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

            with self.lock:
                self.frame = frame

        if self.writer is not None:
            self.writer.release()
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=2)
            self._capture_thread = None
        self.stop_event.set()
