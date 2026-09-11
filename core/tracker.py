from collections import deque
from core.config import config

KNOWN_HEIGHTS = {
    0: 3.0,  # Fence
    1: 1.7,  # Person
}

def estimate_distance(bbox_h_px: float, cls_id: int) -> float:
    """Return estimated distance in metres (1 decimal place)."""
    if bbox_h_px <= 0:
        return 99.9
    height_m = KNOWN_HEIGHTS.get(cls_id, config.person_height_m)
    return round((height_m * config.focal_length_px) / bbox_h_px, 1)

def get_distance_color(dist_m: float) -> tuple[int, int, int]:
    """Return BGR colour for a proximity gauge: green → red."""
    ratio = max(0.0, min(1.0, dist_m / config.alert_dist_m))
    if ratio > 0.8:
        return (0, 200, 0)      # green  — safe
    if ratio > 0.5:
        return (0, 200, 255)    # yellow — approaching
    if ratio > 0.3:
        return (0, 165, 255)    # orange — close
    return (0, 0, 255)          # red    — breach zone

class DistanceTracker:
    """Track targets across frames by centroid proximity and smooth
    bounding box heights with a rolling median filter for more stable distance.
    """
    _WINDOW = 15         # increased window size for smoother tracking
    _MAX_DIST_PX = 120   # max centroid movement (px) to count as "same target"
    _STALE_FRAMES = 15   # drop track after this many unseen frames

    def __init__(self) -> None:
        self._next_id = 1
        # {track_id: {"cx": float, "cy": float, "buf": deque, "age": int}}
        self._tracks: dict[int, dict] = {}

    def update(self, detections: list[tuple[int, int, int, int, float, int]]) -> list[tuple[int, float]]:
        """Accept detections [(x1, y1, x2, y2, bbox_h, cls_id), ...] and
        return [(track_id, smoothed_dist_m), ...] in the same order."""
        used_tracks: set[int] = set()
        results: list[tuple[int, float]] = []

        for x1, y1, x2, y2, bbox_h, cls_id in detections:
            cx = (x1 + x2) / 2.0
            cy = (y1 + y2) / 2.0

            best_tid, best_dist_px = -1, float("inf")
            for tid, t in self._tracks.items():
                if tid in used_tracks:
                    continue
                dx = cx - t["cx"]
                dy = cy - t["cy"]
                d = (dx * dx + dy * dy) ** 0.5
                if d < best_dist_px:
                    best_dist_px = d
                    best_tid = tid

            if best_tid >= 0 and best_dist_px <= self._MAX_DIST_PX:
                tid = best_tid
            else:
                tid = self._next_id
                self._next_id += 1
                self._tracks[tid] = {"cx": cx, "cy": cy,
                                     "buf": deque(maxlen=self._WINDOW), "age": 0}

            track = self._tracks[tid]
            track["cx"] = cx
            track["cy"] = cy
            track["age"] = 0
            track["buf"].append(bbox_h)
            used_tracks.add(tid)

            buf = sorted(track["buf"])
            smoothed_h = buf[len(buf) // 2]
            
            smoothed_dist = estimate_distance(smoothed_h, cls_id)
            results.append((tid, smoothed_dist))

        stale = [tid for tid, t in self._tracks.items()
                 if tid not in used_tracks]
        for tid in stale:
            self._tracks[tid]["age"] += 1
            if self._tracks[tid]["age"] > self._STALE_FRAMES:
                del self._tracks[tid]

        return results
