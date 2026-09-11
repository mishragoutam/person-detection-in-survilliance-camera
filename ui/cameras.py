import os
import json
import datetime
import subprocess
import sys
import threading
import urllib.request
from pathlib import Path
from PIL import Image

import customtkinter as ctk
from ui.theme import COLORS, FONTS, PAD, RADIUS
from ui.widgets import ScrollPage, PageHeader, Pill, Card, PrimaryButton, SecondaryButton

_PROJECT_DIR = Path(__file__).resolve().parent.parent
_ALERTS_DIR = _PROJECT_DIR / "alerts"
_CONFIG_PATH = _PROJECT_DIR / "config.json"
_STREAM_PORT = int(os.getenv("NETRA_STREAM_PORT", "5001"))

def _detector_python():
    candidates = [
        _PROJECT_DIR / ".venv312" / "Scripts" / "python.exe",
        Path(sys.executable),
        Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python312" / "python.exe",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            check = subprocess.run(
                [str(candidate), "-c", "import cv2, ultralytics"],
                capture_output=True, timeout=5,
            )
            if check.returncode == 0:
                return str(candidate)
        except (OSError, subprocess.SubprocessError):
            continue
    return None

CAMERAS = ["Camera 1 — Gate A", "Camera 2 — East Ridge",
           "Camera 3 — North Fence", "Camera 4 — River Bend"]

def _get_camera_choices():
    try:
        with open(_CONFIG_PATH, encoding="utf-8") as file:
            cameras = json.load(file).get("cameras", [])
        choices = [
            f"{camera.get('id', 'CAM')} — {camera.get('name', 'Camera')}"
            for camera in cameras
        ]
        return choices or CAMERAS
    except (OSError, json.JSONDecodeError):
        return CAMERAS

class LiveSurveillancePage(ScrollPage):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.running = False
        self._detector_proc = None
        self._stream_active = False
        self._stream_thread = None
        self._stream_start_after = None
        self._stream_generation = 0
        self._detector_log_thread = None
        self._alert_count = 0
        self._alert_refresh_after = None
        self._seen_alerts = set()

        header_row = ctk.CTkFrame(self, fg_color="transparent")
        header_row.pack(fill="x", pady=(0, PAD["lg"]))
        PageHeader(header_row, "Live Camera Surveillance",
                   "Real-time detection across active border cameras",
                   accent=COLORS["live"]).pack(side="left", fill="x", expand=True)
        self.status_pill = Pill(header_row, "STOPPED", COLORS["text_muted"])
        self.status_pill.pack(side="right")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=3, uniform="body")
        body.grid_columnconfigure(1, weight=2, uniform="body")

        video_card = Card(body)
        video_card.grid(row=0, column=0, sticky="nsew", padx=(0, PAD["md"]))
        vinner = ctk.CTkFrame(video_card, fg_color="transparent")
        vinner.pack(fill="both", expand=True, padx=PAD["md"], pady=PAD["md"])

        controls = ctk.CTkFrame(vinner, fg_color="transparent")
        controls.pack(fill="x", pady=(0, PAD["sm"]))
        self.camera_select = ctk.CTkOptionMenu(
            controls, values=_get_camera_choices(), fg_color=COLORS["bg_panel_alt"],
            button_color=COLORS["bg_panel_alt"], button_hover_color=COLORS["border"],
            text_color=COLORS["text_primary"], font=FONTS["body"])
        self.camera_select.pack(side="left")
        self.start_btn = PrimaryButton(controls, "▶  Start Feed", accent=COLORS["live"],
                                        command=self._toggle_feed)
        self.start_btn.pack(side="right")

        self.video_label = ctk.CTkLabel(
            vinner, text="Camera feed will appear here\n(livedetector.py output)",
            fg_color=COLORS["bg_base"], corner_radius=RADIUS["md"],
            text_color=COLORS["text_muted"], font=FONTS["body"], height=380)
        self.video_label.pack(fill="both", expand=True, pady=(0, PAD["sm"]))

        info_row = ctk.CTkFrame(vinner, fg_color="transparent")
        info_row.pack(fill="x", pady=(0, PAD["sm"]))
        self.frame_state = ctk.CTkLabel(info_row, text="NO SIGNAL", font=FONTS["small_bold"],
                        text_color=COLORS["text_muted"])
        self.frame_state.pack(side="left")
        self.alert_state = ctk.CTkLabel(info_row, text="0 snapshots", font=FONTS["small"],
                        text_color=COLORS["text_secondary"])
        self.alert_state.pack(side="right")

        dist_row = ctk.CTkFrame(vinner, fg_color="transparent")
        dist_row.pack(fill="x")
        ctk.CTkLabel(dist_row, text="Alert Distance", font=FONTS["small"],
                     text_color=COLORS["text_secondary"]).pack(side="left")
        self.dist_value = ctk.CTkLabel(dist_row, text="5.0 m", font=FONTS["small_bold"],
                                        text_color=COLORS["live"])
        self.dist_value.pack(side="right")
        self.dist_slider = ctk.CTkSlider(
            vinner, from_=1, to=20, number_of_steps=38, progress_color=COLORS["live"],
            button_color=COLORS["live"], button_hover_color=COLORS["live"],
            command=self._on_distance_change)
        self.dist_slider.set(5)
        self.dist_slider.pack(fill="x", pady=(4, 0))

        log_card = Card(body)
        log_card.grid(row=0, column=1, sticky="nsew")
        linner = ctk.CTkFrame(log_card, fg_color="transparent")
        linner.pack(fill="both", expand=True, padx=PAD["md"], pady=PAD["md"])
        ctk.CTkLabel(linner, text="Live Event Log", font=FONTS["h2"],
                     text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, PAD["sm"]))
        log_actions = ctk.CTkFrame(linner, fg_color="transparent")
        log_actions.pack(fill="x", pady=(0, PAD["sm"]))
        SecondaryButton(log_actions, "Refresh Alerts", command=self._refresh_alert_log).pack(side="left")
        SecondaryButton(log_actions, "Open Alerts Folder", command=self._open_alerts_folder).pack(side="right")
        self.log_box = ctk.CTkTextbox(
            linner, fg_color=COLORS["bg_base"], text_color=COLORS["text_secondary"],
            font=FONTS["mono"], corner_radius=RADIUS["sm"], wrap="word")
        self.log_box.pack(fill="both", expand=True)
        self.log_box.configure(state="disabled")

        self.log("System initialized. Waiting for feed start…")
        self._refresh_alert_log()

    def _toggle_feed(self):
        self.running = not self.running
        if self.running:
            detector_py = _detector_python()
            if detector_py is None:
                self.running = False
                self.start_btn.configure(text="▶  Start Feed", fg_color=COLORS["live"])
                self.status_pill.configure(text="  UNAVAILABLE  ", fg_color=COLORS["danger"])
                self.log("ERROR: detector dependencies missing. This interpreter needs cv2 and ultralytics.")
                self.log("Install them in the Python environment selected for this workspace, then retry.")
                return
            self.start_btn.configure(text="■  Stop Feed", fg_color=COLORS["danger"])
            self.status_pill.configure(text="  STARTING  ", fg_color=COLORS["warning"])
            self.log(f"Starting livedetector.py on {self.camera_select.get()}...")
            camera_id = self.camera_select.get().split(" — ", 1)[0].strip()
            self._detector_proc = subprocess.Popen(
                [detector_py, "-u", str(_PROJECT_DIR / "livedetector.py"),
                 "--camera-id", camera_id],
                cwd=str(_PROJECT_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            self._detector_log_thread = threading.Thread(
                target=self._read_detector_output, args=(self._detector_proc,), daemon=True
            )
            self._detector_log_thread.start()
            self.log("Detector started. Waiting for stream...")
            self._stream_generation += 1
            generation = self._stream_generation
            self._stream_start_after = self.after(
                200, lambda: self._start_stream_reader(generation)
            )
        else:
            self.start_btn.configure(text="▶  Start Feed", fg_color=COLORS["live"])
            self.status_pill.configure(text="  STOPPED  ", fg_color=COLORS["text_muted"])
            self._stop_stream()
            self.log("Feed stopped.")

    def _read_detector_output(self, process):
        if process.stdout is None:
            return
        for line in process.stdout:
            message = line.strip()
            if message:
                self.after(0, lambda text=message: self.log(f"Detector: {text}"))
        code = process.poll()
        if code not in (None, 0):
            self.after(0, lambda: self._detector_failed(code))

    def _detector_failed(self, code):
        if self.running:
            self.running = False
            self._stream_active = False
            self.status_pill.configure(text="  ERROR  ", fg_color=COLORS["danger"])
            self.start_btn.configure(text="▶  Start Feed", fg_color=COLORS["live"])
            self.log(f"Detector stopped before streaming (exit code {code}).")

    def _refresh_alert_state(self):
        _ALERTS_DIR.mkdir(exist_ok=True)
        self._alert_count = len(list(_ALERTS_DIR.glob("*.jpg")))
        self.alert_state.configure(text=f"{self._alert_count} snapshots")
        if self._alert_refresh_after is None:
            self._alert_refresh_after = self.after(2000, self._run_alert_refresh)

    def _refresh_alert_log(self):
        self._refresh_alert_state()
        files = sorted(_ALERTS_DIR.glob("*.jpg"), key=lambda path: path.stat().st_mtime)
        new_files = [path for path in files if path.name not in self._seen_alerts]
        for path in new_files:
            stamp = datetime.datetime.fromtimestamp(path.stat().st_mtime).strftime("%H:%M:%S")
            self.log(f"ALERT: snapshot captured at {stamp} — {path.name}")
            self._seen_alerts.add(path.name)
        if not new_files:
            self.log("Alerts refreshed: no new snapshots.")

    def _run_alert_refresh(self):
        self._alert_refresh_after = None
        self._refresh_alert_state()

    def _open_alerts_folder(self):
        _ALERTS_DIR.mkdir(exist_ok=True)
        os.startfile(str(_ALERTS_DIR))

    def _start_stream_reader(self, generation):
        if not self.running or generation != self._stream_generation:
            return
        self._stream_start_after = None
        self._stream_active = True
        self._stream_thread = threading.Thread(
            target=self._read_mjpeg, args=(generation,), daemon=True
        )
        self._stream_thread.start()
        self.log("Stream reader started; waiting for first frame...")

    def _read_mjpeg(self, generation):
        import cv2
        stream_url = f"http://127.0.0.1:{_STREAM_PORT}/video_feed"
        cap = cv2.VideoCapture(stream_url)
        connected = False
        while (self._stream_active and self.running
               and generation == self._stream_generation):
            ret, frame = cap.read()
            if not ret:
                import time
                time.sleep(0.15)
                cap.release()
                cap = cv2.VideoCapture(stream_url)
                continue
            if not connected:
                connected = True
                self.after(0, lambda: self._mark_stream_live(generation))
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            pil_img = pil_img.resize((640, 360), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(640, 360))
            self.after(0, lambda img=ctk_img: self.video_label.configure(image=img, text=""))
            import time
            time.sleep(0.033)
        cap.release()

    def _mark_stream_live(self, generation):
        if self.running and generation == self._stream_generation:
            self.status_pill.configure(text="  LIVE  ", fg_color=COLORS["danger"])
            self.frame_state.configure(text="SIGNAL LOCKED", text_color=COLORS["success"])
            self.log("Connected to MJPEG stream on port 5001.")

    def _stop_stream(self):
        self._stream_active = False
        self.frame_state.configure(text="NO SIGNAL", text_color=COLORS["text_muted"])
        self._stream_generation += 1
        if self._stream_start_after is not None:
            try:
                self.after_cancel(self._stream_start_after)
            except Exception:
                pass
            self._stream_start_after = None
        if hasattr(self, '_detector_proc') and self._detector_proc and self._detector_proc.poll() is None:
            try:
                request = urllib.request.Request(
                    f"http://127.0.0.1:{_STREAM_PORT}/shutdown", method="POST"
                )
                urllib.request.urlopen(request, timeout=1).close()
            except Exception:
                pass
            try:
                self._detector_proc.terminate()
                self._detector_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._detector_proc.kill()
                self._detector_proc.wait(timeout=2)
            except Exception:
                pass
            self.log("Detector process terminated.")
        if self._stream_thread and self._stream_thread.is_alive():
            self._stream_thread.join(timeout=2)
        self._stream_thread = None
        self._detector_proc = None
        
        try:
            self.video_label.configure(image=None, text="Camera feed will appear here\n(livedetector.py output)")
        except Exception:
            pass

    def _on_distance_change(self, value):
        self.dist_value.configure(text=f"{value:.1f} m")
        try:
            with open(_CONFIG_PATH, "r") as f:
                cfg = json.load(f)
            if "distance" not in cfg:
                cfg["distance"] = {}
            cfg["distance"]["alert_threshold_meters"] = round(value, 1)
            with open(_CONFIG_PATH, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception as e:
            self.log(f"Error saving distance: {e}")

    def log(self, message: str):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{ts}] {message}\n")
        self.log_box.configure(state="disabled")
        self.log_box.see("end")
