"""
api_server.py — NETRA REST API + MJPEG stream server
Run alongside livedetector.py to expose APIs to the mobile app.

Endpoints:
  GET  /video_feed          — MJPEG live stream
  GET  /api/status          — system health & camera status
  GET  /api/events          — paginated event history (JSON)
  GET  /api/alerts          — alias for events (mobile-friendly)
  GET  /api/alerts/<id>     — single event detail
  GET  /api/snapshot/<id>   — serve snapshot image for an event
  GET  /api/recording/<id>  — serve threat recording video
  GET  /api/vapid-public-key — VAPID public key for push subscription
  POST /api/subscribe        — register push notification subscription
  DELETE /api/subscribe      — unregister push subscription
  POST /api/test-alert       — trigger test push notification
  POST /api/dismiss/<id>     — mark event as dismissed
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from flask import Flask, Response, jsonify, request, send_file, abort
from flask_cors import CORS
from werkzeug.serving import make_server

from storage.database import EventStore
from services.push_service import (
    add_subscription, remove_subscription, get_public_vapid_key,
    send_test_notification, get_subscription_count,
)

logger = logging.getLogger("netra.api_server")

_PROJECT_DIR = Path(__file__).resolve().parent
_ALERTS_DIR = _PROJECT_DIR / "alerts"
_EVIDENCE_DIR = _PROJECT_DIR / "evidence"

# Shared frame store — camera threads write here, API reads here
_frame_store: dict[str, np.ndarray] = {}
_frame_lock = threading.Lock()


def update_frame(camera_id: str, frame: np.ndarray) -> None:
    """Called by camera threads to push the latest annotated frame."""
    with _frame_lock:
        _frame_store[camera_id] = frame.copy()


def create_api_app(event_store: EventStore) -> Flask:
    # Serve mobile_app directory at root
    app = Flask(__name__, static_folder=str(_PROJECT_DIR / "mobile_app"), static_url_path="")
    CORS(app, origins="*", supports_credentials=False)

    @app.route("/")
    def serve_index():
        response = app.send_static_file("index.html")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
        
    @app.route("/shutdown", methods=["POST"])
    def shutdown():
        import os
        os._exit(0)
        return "OK"

    # ── Live stream ──────────────────────────────────────────────────────────

    def _generate_mjpeg():
        while True:
            with _frame_lock:
                frames = list(_frame_store.values())

            if not frames:
                f = np.zeros((360, 640, 3), dtype=np.uint8)
                cv2.putText(f, "Waiting for cameras...", (30, 180),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.85, (80, 80, 80), 2)
                frames = [f]

            if len(frames) == 1:
                grid = frames[0]
            else:
                rows = []
                for i in range(0, len(frames), 2):
                    pair = frames[i: i + 2]
                    if len(pair) == 1:
                        pair.append(np.zeros_like(pair[0]))
                    rows.append(np.hstack([cv2.resize(f, (640, 360)) for f in pair]))
                grid = np.vstack(rows)

            ret, buf = cv2.imencode(".jpg", grid, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ret:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                       + buf.tobytes() + b"\r\n")
            time.sleep(0.05)

    @app.route("/video_feed")
    def video_feed():
        return Response(_generate_mjpeg(),
                        mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/api/snapshot/live")
    def live_snapshot():
        """Return the latest frame as a JPEG snapshot."""
        with _frame_lock:
            frames = list(_frame_store.values())
        if not frames:
            abort(503, description="No cameras active")
        ret, buf = cv2.imencode(".jpg", frames[0])
        if not ret:
            abort(500)
        return Response(buf.tobytes(), mimetype="image/jpeg")

    # ── System status ────────────────────────────────────────────────────────

    @app.route("/api/status")
    def status():
        with _frame_lock:
            active_cams = list(_frame_store.keys())
        events = event_store.list_events(limit=1)
        last_event = events[0] if events else None
        return jsonify({
            "ok": True,
            "active_cameras": active_cams,
            "camera_count": len(active_cams),
            "subscribers": get_subscription_count(),
            "last_event": last_event,
            "server_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

    # ── Events / Alerts ──────────────────────────────────────────────────────

    def _serialize_event(row: dict[str, Any]) -> dict[str, Any]:
        """Convert raw DB row to API-friendly dict."""
        meta = {}
        try:
            meta = json.loads(row.get("metadata_json") or "{}")
        except Exception:
            pass
        evidence_path = row.get("evidence_path") or ""
        event_id = row.get("event_id", "")

        # Determine snapshot & recording URLs
        snapshot_url = None
        recording_url = None
        if evidence_path:
            ep = Path(evidence_path)
            if ep.exists():
                snapshot_url = f"/api/snapshot/{event_id}"
            # Check for matching recording (.avi/.mp4)
            for ext in (".avi", ".mp4"):
                rec_path = ep.with_suffix(ext)
                if rec_path.exists():
                    recording_url = f"/api/recording/{event_id}"
                    break

        return {
            "id": event_id,
            "timestamp": row.get("created_at"),
            "camera_id": row.get("camera_id"),
            "location": row.get("location"),
            "event_type": row.get("event_type"),
            "severity": row.get("severity"),
            "score": row.get("score"),
            "confidence": row.get("confidence"),
            "distance_m": row.get("distance_m"),
            "status": row.get("status"),
            "labels": meta.get("labels", []),
            "distances": meta.get("distances", []),
            "snapshot_url": snapshot_url,
            "recording_url": recording_url,
            "has_snapshot": snapshot_url is not None,
            "has_recording": recording_url is not None,
        }

    @app.route("/api/events")
    @app.route("/api/alerts")
    def list_events():
        limit = min(int(request.args.get("limit", 50)), 200)
        rows = event_store.list_events(limit=limit)
        return jsonify({
            "events": [_serialize_event(r) for r in rows],
            "count": len(rows),
        })

    @app.route("/api/alerts/<event_id>")
    @app.route("/api/events/<event_id>")
    def get_event(event_id: str):
        rows = event_store.list_events(limit=1000)
        for row in rows:
            if row.get("event_id") == event_id:
                return jsonify(_serialize_event(row))
        abort(404, description="Event not found")

    @app.route("/api/dismiss/<event_id>", methods=["POST"])
    def dismiss_event(event_id: str):
        event_store.update_status(event_id, "DISMISSED")
        return jsonify({"ok": True, "event_id": event_id})

    # ── Media serving ─────────────────────────────────────────────────────────

    @app.route("/api/snapshot/<event_id>")
    def serve_snapshot(event_id: str):
        rows = event_store.list_events(limit=1000)
        for row in rows:
            if row.get("event_id") == event_id:
                path = row.get("evidence_path")
                if path and Path(path).exists():
                    return send_file(str(Path(path).resolve()), mimetype="image/jpeg")
        abort(404, description="Snapshot not found")

    @app.route("/api/recording/<event_id>")
    def serve_recording(event_id: str):
        rows = event_store.list_events(limit=1000)
        for row in rows:
            if row.get("event_id") == event_id:
                path = row.get("evidence_path")
                if path:
                    ep = Path(path)
                    for ext in (".avi", ".mp4"):
                        rec = ep.with_suffix(ext)
                        if rec.exists():
                            return send_file(
                                str(rec.resolve()),
                                mimetype="video/x-msvideo" if ext == ".avi" else "video/mp4",
                                as_attachment=False,
                            )
        abort(404, description="Recording not found")

    # ── Push notifications ────────────────────────────────────────────────────

    @app.route("/api/vapid-public-key")
    def vapid_public_key():
        key = get_public_vapid_key()
        if not key:
            return jsonify({"error": "VAPID keys not configured"}), 503
        return jsonify({"publicKey": key})

    @app.route("/api/subscribe", methods=["POST"])
    def subscribe():
        data = request.get_json(force=True, silent=True) or {}
        if not data.get("endpoint"):
            return jsonify({"error": "Invalid subscription"}), 400
        added = add_subscription(data)
        return jsonify({"ok": True, "added": added, "subscribers": get_subscription_count()})

    @app.route("/api/subscribe", methods=["DELETE"])
    def unsubscribe():
        data = request.get_json(force=True, silent=True) or {}
        endpoint = data.get("endpoint", "")
        removed = remove_subscription(endpoint)
        return jsonify({"ok": True, "removed": removed})

    @app.route("/api/test-alert", methods=["POST"])
    def test_alert():
        sent = send_test_notification()
        return jsonify({
            "ok": True,
            "sent_to": sent,
            "subscribers": get_subscription_count(),
        })

    return app


class ApiServer:
    """Wraps the Flask API in a background thread with clean start/stop."""

    def __init__(self, host: str, port: int, event_store: EventStore):
        self.host = host
        self.port = port
        self.app = create_api_app(event_store)
        self._server = None
        self._thread = None

    def start(self) -> None:
        self._server = make_server(self.host, self.port, self.app, threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("NETRA API server running at http://%s:%s", self.host, self.port)

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
        if self._thread:
            self._thread.join(timeout=5)
