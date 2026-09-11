"""Low-overhead host metrics for the System page."""

from __future__ import annotations

import os
import threading
from typing import Any


def collect_metrics() -> dict[str, Any]:
    """Return best-effort process and host metrics without failing the UI."""
    metrics: dict[str, Any] = {
        "pid": os.getpid(),
        "threads": threading.active_count(),
        "cpu_percent": None,
        "memory_percent": None,
        "gpu": "Unavailable",
    }
    try:
        import psutil
        process = psutil.Process()
        metrics["cpu_percent"] = process.cpu_percent(interval=0.05)
        metrics["memory_percent"] = process.memory_percent()
        metrics["rss_mb"] = round(process.memory_info().rss / 1024 / 1024, 1)
    except Exception:
        pass
    try:
        import torch
        if torch.cuda.is_available():
            device = torch.cuda.current_device()
            metrics["gpu"] = torch.cuda.get_device_name(device)
            metrics["vram_used_mb"] = round(torch.cuda.memory_allocated(device) / 1024 / 1024, 1)
            metrics["vram_total_mb"] = round(torch.cuda.get_device_properties(device).total_memory / 1024 / 1024, 1)
    except Exception:
        pass
    return metrics
