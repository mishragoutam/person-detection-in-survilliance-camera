"""
demo.py — SIH26187 Border Surveillance Command Center
Run: python demo.py
"""

from __future__ import annotations

import datetime
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter import ttk
import tkinter as tk
from typing import Any

import cv2
import numpy as np

# ── Config ──────────────────────────────────────────────────────
_CONFIG_PATH = Path(__file__).parent / "config.json"

def _load_config() -> dict[str, Any]:
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {}

_cfg: dict[str, Any] = _load_config()
_dist_cfg: dict[str, Any] = _cfg.get("distance", {})
ALERT_DIST_M: float = float(_dist_cfg.get("alert_threshold_meters", 5.0))
FOCAL_LEN: float = float(_dist_cfg.get("focal_length_px", 700))
PERSON_H: float = float(_dist_cfg.get("known_person_height_m", 1.7))

WANTED_CLASSES: list[int] = [0, 2, 3, 5, 7]
CLASS_NAMES: dict[int, str] = {
    0: "Intruder", 2: "Vehicle", 3: "Motorcycle", 5: "Bus", 7: "Truck"
}
CLASS_COLORS: dict[int, tuple[int, int, int]] = {
    0: (0, 0, 255), 2: (0, 165, 255), 3: (0, 165, 255),
    5: (0, 0, 200), 7: (255, 0, 200),
}

# ── Helpers ──────────────────────────────────────────────────────
def _get_best_weights() -> str:
    project_dir = Path(__file__).parent
    for p in [
        project_dir / "runs" / "detect" / "border_surveillance" / "sih26187_final" / "weights" / "best.pt",
        project_dir / "border_surveillance" / "sih26187_final" / "weights" / "best.pt",
        project_dir / "yolov8n.pt",
    ]:
        if p.exists():
            return str(p)
    raise FileNotFoundError("No YOLO weights found, including the trained best.pt checkpoint.")


def _estimate_distance(bbox_h_px: int) -> float:
    if bbox_h_px <= 0:
        return 99.9
    return round((PERSON_H * FOCAL_LEN) / bbox_h_px, 1)


def _get_python_exe() -> str:
    venv312 = Path(r"c:\Users\mishr\OneDrive\Desktop\SIH26\.venv312\Scripts\python.exe")
    if venv312.exists():
        return str(venv312)
    return sys.executable


# ── Video analysis (runs in background thread) ─────────────────
def _video_worker(video_path: str, status: tk.StringVar) -> None:
    """Runs YOLO detection on a video file in its own thread."""
    try:
        from ultralytics import YOLO  # type: ignore
    except ImportError:
        messagebox.showerror(
            "Missing package",
            "ultralytics is not installed.\nRun: pip install ultralytics"
        )
        return

    weights: str = _get_best_weights()
    status.set(f"Loading model: {Path(weights).name} …")
    model = YOLO(weights)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        messagebox.showerror("Error", f"Cannot open video:\n{video_path}")
        status.set("Ready")
        return

    W: int = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
    H: int = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
    border_y: int = int(H * 0.60)

    win_name: str = "SIH26187 — Video Analysis  (Q / ESC = quit)"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, min(W, 1280), min(H, 720))
    status.set(f"Analyzing: {Path(video_path).name}")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        results = model(frame, classes=WANTED_CLASSES, verbose=False)
        boxes = results[0].boxes if len(results) > 0 else []  # type: ignore
        threat: bool = False

        # Border tripwire
        cv2.line(frame, (0, border_y), (W, border_y), (0, 255, 255), 2)
        cv2.putText(
            frame, f"BORDER LINE  |  Alert if < {ALERT_DIST_M} m",
            (15, border_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2,
        )

        if boxes is not None:
            for box in boxes:  # type: ignore
                cls_id: int = int(box.cls[0])
                conf: float = float(box.conf[0])
                name: str = CLASS_NAMES.get(cls_id, "Object")
                color: tuple[int, int, int] = CLASS_COLORS.get(cls_id, (255, 255, 255))
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                dist_m: float = _estimate_distance(y2 - y1)

                if y2 > border_y and dist_m <= ALERT_DIST_M:
                    threat = True
                    color = (0, 0, 255)

                lbl = f"{name} {conf:.0%} | {dist_m} m"
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                (lw, lh), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
                cv2.rectangle(frame, (x1, y1 - lh - 8), (x1 + lw + 6, y1), color, -1)
                cv2.putText(frame, lbl, (x1 + 3, y1 - 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        if threat:
            cv2.putText(
                frame, "!! THREAT — BORDER BREACH !!",
                (W // 2 - 240, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 255), 3,
            )

        ts: str = datetime.datetime.now().strftime("%H:%M:%S  %d-%b-%Y")
        tw, _ = cv2.getTextSize(ts, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)[0]
        cv2.putText(frame, ts, (W - tw - 10, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 1)
        
        box_count = len(boxes) if boxes is not None else 0  # type: ignore
        cv2.putText(frame, f"Objects: {box_count} | Alert: <{ALERT_DIST_M} m",
                    (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

        cv2.imshow(win_name, frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break
        try:
            if cv2.getWindowProperty(win_name, cv2.WND_PROP_VISIBLE) < 1:
                break
        except Exception:
            break

    cap.release()
    cv2.destroyAllWindows()
    status.set("Ready")


# ── Button callbacks ───────────────────────────────────────────
def run_video(status_var: tk.StringVar, parent: tk.Tk) -> None:
    video_path: str = filedialog.askopenfilename(
        title="Select CCTV Security Footage",
        parent=parent,
        filetypes=[
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv"),
            ("All files", "*.*"),
        ],
    )
    if not video_path:
        return
    threading.Thread(
        target=_video_worker, args=(video_path, status_var), daemon=True
    ).start()


def run_live(status_var: tk.StringVar, parent: tk.Tk) -> None:
    py: str = _get_python_exe()
    ld: str = str(Path(__file__).parent / "livedetector.py")
    cwd: str = str(Path(__file__).parent)

    def _worker() -> None:
        parent.withdraw()
        status_var.set("Live surveillance running …")
        try:
            subprocess.run([py, ld], cwd=cwd, check=False)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to start live detector:\n{exc}")
        finally:
            parent.deiconify()
            status_var.set("Ready")

    threading.Thread(target=_worker, daemon=True).start()


def open_folder(name: str) -> None:
    p = Path(name)
    p.mkdir(exist_ok=True)
    os.startfile(str(p.resolve()))


def open_training_graphs() -> None:
    for p in [
        "runs/detect/border_surveillance/sih26187_final",
        "runs/detect/border_surveillance",
        "runs",
    ]:
        if Path(p).exists():
            os.startfile(str(Path(p).resolve()))
            return
    messagebox.showinfo(
        "Not found", "No training results yet.\nRun train_gpu.py first."
    )


def open_config() -> None:
    if _CONFIG_PATH.exists():
        os.startfile(str(_CONFIG_PATH.resolve()))
    else:
        messagebox.showinfo("Config", f"config.json not found at:\n{_CONFIG_PATH}")


# ── UI ──────────────────────────────────────────────────────────
def _build_ui() -> None:
    root = tk.Tk()
    root.title("SIH26187 — Border Surveillance Command Center")
    root.geometry("490x480")
    root.resizable(False, False)
    root.configure(bg="#1e1e2e")

    tk.Label(
        root,
        text="🛡️ SIH26187 — Border Surveillance\nAI-Based Intelligent Video Analytics Platform",
        font=("Helvetica", 13, "bold"),
        fg="#89b4fa",
        bg="#1e1e2e",
        justify="center",
    ).pack(pady=12)

    tk.Label(
        root,
        text=f"Ministry of Home Affairs  |  Alert distance: {ALERT_DIST_M} m",
        font=("Helvetica", 9),
        fg="#6c7086",
        bg="#1e1e2e",
    ).pack()

    ttk.Separator(root, orient="horizontal").pack(fill="x", padx=20, pady=10)

    btn_kw: dict[str, Any] = dict(
        font=("Helvetica", 11, "bold"), width=38, bd=0,
        cursor="hand2", padx=8, pady=7,
    )

    status_var = tk.StringVar(value="Ready")

    tk.Button(
        root, text="📹  Live Border Camera Surveillance",
        bg="#a6e3a1", fg="#11111b",
        command=lambda: run_live(status_var, root),
        **btn_kw,
    ).pack(pady=4)

    tk.Button(
        root, text="🎬  Analyze CCTV Video File",
        bg="#89dceb", fg="#11111b",
        command=lambda: run_video(status_var, root),
        **btn_kw,
    ).pack(pady=4)

    tk.Button(
        root, text="👤  Authorized Personnel Whitelist  (authorized/)",
        bg="#f9e2af", fg="#11111b",
        command=lambda: open_folder("authorized"),
        **btn_kw,
    ).pack(pady=4)

    tk.Button(
        root, text="📸  View Threat Evidence & Snapshots  (alerts/)",
        bg="#eba0ac", fg="#11111b",
        command=lambda: open_folder("alerts"),
        **btn_kw,
    ).pack(pady=4)

    tk.Button(
        root, text="📊  AI Training Graphs & Metrics",
        bg="#cba6f7", fg="#11111b",
        command=open_training_graphs,
        **btn_kw,
    ).pack(pady=4)

    tk.Button(
        root, text="⚙️  Edit Config (cameras / distance / Telegram)",
        bg="#f38ba8", fg="#11111b",
        command=open_config,
        **btn_kw,
    ).pack(pady=4)

    ttk.Separator(root, orient="horizontal").pack(fill="x", padx=20, pady=8)

    tk.Label(
        root, textvariable=status_var,
        font=("Helvetica", 9, "italic"),
        fg="#a6e3a1", bg="#1e1e2e",
    ).pack()

    root.mainloop()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, help="Path to video file for analysis")
    args = parser.parse_args()

    if args.video:
        # Create a dummy tkinter root and stringvar so _video_worker doesn't crash on messagebox/status updates
        root = tk.Tk()
        root.withdraw()
        status_var = tk.StringVar()
        _video_worker(args.video, status_var)
    else:
        _build_ui()
