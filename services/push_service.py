"""
push_service.py — Web Push notification service for NETRA surveillance system.
Replaces Telegram alerts with browser Web Push notifications (VAPID protocol).
Subscriptions are stored persistently in push_subscriptions.json.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("netra.push_service")

_PROJECT_DIR = Path(__file__).resolve().parent.parent
_SUBS_FILE = _PROJECT_DIR / "push_subscriptions.json"
_VAPID_FILE = _PROJECT_DIR / "vapid_keys.json"
_lock = threading.Lock()


# ── VAPID key management ──────────────────────────────────────────────────────

def generate_vapid_keys() -> dict[str, str]:
    """Generate VAPID key pair and save to vapid_keys.json."""
    try:
        from py_vapid import Vapid
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    except ImportError:
        logger.error("py_vapid not installed. Run: pip install py-vapid pywebpush")
        return {}

    vapid = Vapid()
    vapid.generate_keys()
    private_pem = vapid.private_pem().decode()
    public_pem = vapid.public_key.public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    keys = {"private_key": private_pem, "public_key": public_pem}
    _VAPID_FILE.write_text(json.dumps(keys, indent=2), encoding="utf-8")
    logger.info("VAPID keys generated and saved to %s", _VAPID_FILE)
    return keys


def get_vapid_keys() -> dict[str, str]:
    """Load or generate VAPID keys."""
    if _VAPID_FILE.exists():
        try:
            return json.loads(_VAPID_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return generate_vapid_keys()


def get_public_vapid_key() -> str:
    """Return the raw base64url public key for the browser (uncompressed point format)."""
    try:
        from py_vapid import Vapid
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
        import base64
    except ImportError:
        return ""

    keys = get_vapid_keys()
    if not keys or "private_key" not in keys:
        return ""
    try:
        vapid = Vapid.from_pem(keys["private_key"].encode())
        raw = vapid.public_key.public_bytes(
            encoding=Encoding.X962,
            format=PublicFormat.UncompressedPoint,
        )
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    except Exception as exc:
        logger.warning("Could not get public VAPID key: %s", exc)
        return ""


# ── Subscription management ───────────────────────────────────────────────────

def _load_subscriptions() -> list[dict]:
    if not _SUBS_FILE.exists():
        return []
    try:
        return json.loads(_SUBS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_subscriptions(subs: list[dict]) -> None:
    _SUBS_FILE.write_text(json.dumps(subs, indent=2), encoding="utf-8")


def add_subscription(subscription: dict) -> bool:
    """Register a new push subscription endpoint. Returns True if newly added."""
    with _lock:
        subs = _load_subscriptions()
        endpoint = subscription.get("endpoint", "")
        if any(s.get("endpoint") == endpoint for s in subs):
            logger.debug("Subscription already registered: %s", endpoint[:60])
            return False
        subs.append(subscription)
        _save_subscriptions(subs)
        logger.info("New push subscription registered (%d total)", len(subs))
        return True


def remove_subscription(endpoint: str) -> bool:
    """Unregister a push subscription by endpoint URL."""
    with _lock:
        subs = _load_subscriptions()
        new_subs = [s for s in subs if s.get("endpoint") != endpoint]
        if len(new_subs) == len(subs):
            return False
        _save_subscriptions(new_subs)
        logger.info("Push subscription removed (%d remaining)", len(new_subs))
        return True


def get_subscription_count() -> int:
    with _lock:
        return len(_load_subscriptions())


# ── Push sending ──────────────────────────────────────────────────────────────

def _send_to_one(subscription: dict, payload: str, vapid_claims: dict, private_key: str) -> bool:
    """Send push notification to a single subscription. Returns False if expired."""
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.error("pywebpush not installed. Run: pip install pywebpush")
        return True  # Don't remove sub

    try:
        webpush(
            subscription_info=subscription,
            data=payload,
            vapid_private_key=private_key,
            vapid_claims=vapid_claims,
        )
        return True
    except Exception as exc:
        exc_str = str(exc)
        if "410" in exc_str or "404" in exc_str:
            logger.info("Subscription expired, will remove: %s", subscription.get("endpoint", "")[:60])
            return False
        logger.warning("Push send failed: %s", exc_str[:120])
        return True


def send_alert_notification(
    camera: dict[str, Any],
    labels: list[str],
    distances: list[float],
    snapshot_url: str | None = None,
) -> int:
    """
    Send Web Push alert notification to all subscribed devices.
    Returns number of successful sends.
    """
    keys = get_vapid_keys()
    if not keys or "private_key" not in keys:
        logger.warning("VAPID keys not available — push notification skipped")
        return 0

    dets = ", ".join(set(labels)) if labels else "Intruder"
    dists = ", ".join(f"{d}m" for d in distances) if distances else "Unknown"
    cam_name = camera.get("name", camera.get("id", "Camera"))
    loc = camera.get("location", {})
    loc_label = loc.get("label", cam_name)

    payload = json.dumps({
        "title": "🚨 BORDER BREACH DETECTED",
        "body": f"{cam_name} | {dets} @ {dists}\n📍 {loc_label}",
        "icon": "/icon-192.png",
        "badge": "/badge-72.png",
        "tag": f"alert-{camera.get('id', 'CAM-01')}",
        "renotify": True,
        "data": {
            "camera_id": camera.get("id", "CAM-01"),
            "camera_name": cam_name,
            "location": loc_label,
            "lat": float(loc.get("lat", 0)),
            "lon": float(loc.get("lon", 0)),
            "labels": labels,
            "distances": distances,
            "snapshot_url": snapshot_url,
            "url": "/alerts",
        },
    })

    vapid_claims = {
        "sub": "mailto:surveillance@netra.local",
    }

    with _lock:
        subs = _load_subscriptions()

    if not subs:
        logger.debug("No push subscribers — skipping notification")
        return 0

    expired = []
    success = 0

    def _send(sub: dict) -> None:
        nonlocal success
        ok = _send_to_one(sub, payload, vapid_claims, keys["private_key"])
        if ok:
            success += 1
        else:
            expired.append(sub.get("endpoint", ""))

    threads = [threading.Thread(target=_send, args=(s,), daemon=True) for s in subs]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    # Clean up expired subscriptions
    if expired:
        with _lock:
            current = _load_subscriptions()
            _save_subscriptions([s for s in current if s.get("endpoint") not in expired])

    logger.info("Push notifications sent: %d/%d", success, len(subs))
    return success


def send_test_notification() -> int:
    """Send a test push notification to all subscribers."""
    return send_alert_notification(
        camera={"id": "TEST", "name": "Test Camera", "location": {"label": "Test Location", "lat": 0, "lon": 0}},
        labels=["Test Alert"],
        distances=[3.5],
        snapshot_url=None,
    )
