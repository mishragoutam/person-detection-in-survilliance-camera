import logging
import requests
import datetime
from pathlib import Path

logger = logging.getLogger("netra.telegram")

def send_telegram_alert(
    token: str,
    chat_id: str,
    snapshot_path: str,
    camera: dict,
    labels: list[str],
    distances: list[float],
) -> None:
    """Send photo + GPS pin to Telegram."""
    if not token or not chat_id:
        return
    loc     = camera.get("location", {})
    lat     = float(loc.get("lat", 0.0))
    lon     = float(loc.get("lon", 0.0))
    loc_lbl = str(loc.get("label", camera.get("name", "Border Post")))
    dets    = ", ".join(set(labels)) if labels else "Intruder"
    dists   = ", ".join(f"{d} m" for d in distances) if distances else "Unknown"
    ts      = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    caption = (
        f"🚨 *BORDER ALERT — SIH26187*\n"
        f"📹 {camera.get('id', 'CAM-01')} | {camera.get('name', 'Gate')}\n"
        f"📍 {loc_lbl}\n"
        f"🌐 GPS: `{lat}, {lon}`\n"
        f"⚠️ Detected: *{dets}*\n"
        f"📏 Distance: *{dists}*\n"
        f"🕐 {ts}\n"
        f"[📌 Google Maps](https://maps.google.com/?q={lat},{lon})"
    )
    try:
        with open(snapshot_path, "rb") as photo:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data={
                    "chat_id": chat_id,
                    "caption": caption,
                    "parse_mode": "Markdown",
                },
                files={"photo": photo},
                timeout=8,
            )
            response.raise_for_status()
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendLocation",
            data={
                "chat_id": chat_id,
                "latitude": lat,
                "longitude": lon,
            },
            timeout=8,
        )
        response.raise_for_status()
        logger.info("Telegram alert sent for %s", camera.get("id", "CAM-01"))
    except Exception as exc:
        logger.warning("Telegram alert failed: %s", exc)
