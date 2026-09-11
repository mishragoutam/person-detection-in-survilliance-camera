# NETRA Border Surveillance Command Center

NETRA is a Windows desktop command center for AI-assisted border surveillance. It provides a CustomTkinter interface for live camera monitoring, offline CCTV analysis, authorized-person management, threat evidence review, training metrics, and configuration.

`netra_app.py` is the main entry point.

## Features

- Dashboard with alert, whitelist, and Telegram status counts.
- Live surveillance through `livedetector.py`.
- Offline CCTV analysis through `demo.py`.
- Authorized personnel image management.
- Threat snapshot and recorded-event browsing.
- Training metric charts from YOLO `results.csv`, with built-in demo values if no CSV exists.
- Configuration editing for cameras, distance estimation, alert cooldown, and Telegram notifications.

## Requirements

- Windows with a working desktop session. Tkinter/CustomTkinter needs a graphical display.
- Python 3.11 or 3.12 recommended.
- A webcam, RTSP stream, or supported video file for detection operations.
- Python packages:
  - `customtkinter`
  - `Pillow`
  - `opencv-python`
  - `numpy`
  - `requests`
  - `flask`
  - `ultralytics`
  - `torch`
- An NVIDIA GPU is optional. CPU inference works but is slower.
- Internet access is needed the first time Ultralytics downloads a model or when Telegram alerts are sent.

The dependency list is also recorded in `requirements.txt`. Install it in a virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run the program with the environment's interpreter directly:

```powershell
.\.venv\Scripts\python.exe netra_app.py
```

## Run

Run from the project directory so all relative detector paths resolve correctly:

```powershell
cd C:\Users\mishr\OneDrive\Desktop\SIH26
python netra_app.py
```

The GUI opens on the Dashboard. Close the detector window and stop the feed before exiting the application.

## Files Required by Operation

### Minimum dashboard startup

These are required to start the GUI reliably:

| Path | Required | Purpose |
| --- | --- | --- |
| `netra_app.py` | Yes | Main CustomTkinter application, widgets, pages, navigation, and callbacks. The logo is embedded in this file. |
| `config.json` | Recommended | Camera, distance, cooldown, and Telegram settings. The GUI has defaults if it is absent, but Live Surveillance creates/uses it. |
| Python standard library | Yes | `json`, `pathlib`, `threading`, `subprocess`, Tkinter, and other built-ins used by the app. |
| `customtkinter` | Yes | GUI framework. |
| `Pillow` | Yes | Loads alert thumbnails and converts the live MJPEG frames for display. |

The `alerts/` and `authorized/` directories are created automatically when needed. They may be empty at first.

### Live Camera Surveillance

Required:

- `netra_app.py`
- `livedetector.py`
- `config.json`
- `ultralytics`, `torch`, `opencv-python`, `numpy`, `requests`, and `flask`
- A model file. The detector checks these paths in this order:
  1. `runs/detect/border_surveillance/sih26187_final/weights/best.pt`
  2. `border_surveillance/sih26187_final/weights/best.pt`
  3. `yolov8n.pt`
- A camera index such as `0`, or a reachable RTSP/HTTP/video source in `config.json`.

What happens:

1. The GUI starts `livedetector.py` as a subprocess using `.venv312\Scripts\python.exe` when that interpreter exists; otherwise it uses the current Python interpreter.
2. `livedetector.py` loads the model and starts one `CameraThread` per configured camera.
3. Each thread reads frames, detects configured classes, estimates distance, checks the authorized whitelist, and creates an MJPEG server at `http://127.0.0.1:5001/video_feed`.
4. The GUI connects to that stream and displays it.
5. A non-whitelisted person within the configured distance creates a snapshot in `alerts/`. Recording continues briefly and can trigger Telegram photo/GPS notifications.

Important: the camera dropdown in the GUI is currently visual only. The detector uses every camera listed in `config.json`; changing the dropdown does not select a different detector source.

### Analyze CCTV Video File

Required:

- `netra_app.py`
- `demo.py`
- A supported video file: `.mp4`, `.avi`, `.mov`, `.mkv`, `.wmv`, or `.flv`
- `ultralytics`, `torch`, `opencv-python`, and `numpy`
- One of the model files listed above

The GUI launches:

```powershell
python demo.py --video <path-to-video>
```

`demo.py` performs offline YOLO detection in a separate OpenCV window. The GUI shows start/finish status; the annotated video is displayed by the popup window. Press `Q` or `Esc` in that window to stop analysis.

You can also run analysis directly:

```powershell
python demo.py --video .\path\to\cctv.mp4
```

### Authorized Personnel

Required:

- `authorized/` directory, created automatically if absent
- `.jpg`, `.jpeg`, or `.png` face images placed in `authorized/`

The GUI derives the displayed name from each filename. For example, `raj_kumar.jpg` appears as `Raj Kumar`. `livedetector.py` loads these images at startup, creates HSV/grayscale templates, and uses them to exclude recognized people from threat alerts.

This is image-template matching, not a full identity-management system. Use clear, front-facing reference images and verify results in the actual camera environment.

### Threat Evidence

Required:

- `alerts/` directory, created automatically if absent

Live detection writes:

- `alerts/<camera-id>_<timestamp>.jpg` for threat snapshots
- `alerts/<camera-id>_<timestamp>.avi` for short event recordings

The Dashboard and Evidence page read `.jpg` files from this directory. Existing evidence is optional; without it the pages show an empty state.

### AI Training Graphs

Optional:

- `runs/detect/border_surveillance/sih26187_final/results.csv`, or
- `border_surveillance/sih26187_final/results.csv`

If a valid YOLO `results.csv` is found, the page reads `metrics/mAP50(B)` and training `box_loss`. If it is not found, the UI displays built-in placeholder metric arrays. The four headline values shown on the page are currently static display values.

### Edit Config

Required/recommended:

- `config.json`, located beside `netra_app.py`

The page reads and writes this file. Important fields:

```json
{
  "telegram": {
    "bot_token": "",
    "chat_id": ""
  },
  "alert_cooldown_seconds": 5,
  "distance": {
    "alert_threshold_meters": 20.0,
    "focal_length_px": 700,
    "known_person_height_m": 1.7
  },
  "cameras": [
    {
      "id": "CAM-01",
      "name": "Main Gate",
      "source": 0,
      "location": {
        "lat": 28.6139,
        "lon": 77.209,
        "label": "Main Gate - Sector 1"
      }
    }
  ]
}
```

`source` may be an integer webcam index or a string such as an RTSP URL. Leave `bot_token` and `chat_id` blank to disable Telegram alerts. Treat the bot token as a secret and do not commit it to source control.

## `netra_app.py` Structure and Functions

`netra_app.py` is intentionally a single-file GUI. Its main sections are:

| Symbol | Responsibility |
| --- | --- |
| `get_logo_image()` | Decodes the embedded logo and caches `CTkImage` instances. |
| `Sidebar` | Navigation buttons and active-page highlighting. |
| `PageHeader`, `Card`, `StatTile`, `Pill` | Reusable visual components. |
| `PrimaryButton`, `SecondaryButton`, `ScrollPage` | Reusable controls and page base class. |
| `_get_live_stats()` | Counts alert images, authorized images, and Telegram configuration state. |
| `_get_recent_alerts()` | Reads the newest alert JPG metadata for the Dashboard. |
| `DashboardPage` | Displays system statistics, recent alerts, and quick actions. |
| `LiveSurveillancePage` | Starts/stops `livedetector.py`, reads port 5001, and updates distance configuration. |
| `AnalyzeVideoPage` | Selects a video and starts `demo.py --video ...` in a background thread. |
| `_load_authorized_personnel()` / `WhitelistPage` | Lists, adds, searches, and removes whitelist images. |
| `_load_evidence()` / `EvidencePage` | Loads and filters threat snapshots from `alerts/`. |
| `_load_training_metrics()` | Loads training CSV data or fallback demo arrays. |
| `MiniLineChart` / `TrainingMetricsPage` | Draws accuracy and loss charts. |
| `ConfigPage` | Edits Telegram, timing, distance, and camera settings. |
| `PAGE_REGISTRY` | Maps navigation keys to page classes. |
| `App` | Creates the main window and switches between pages. |

## Detector Functions

### `livedetector.py`

- `estimate_distance()`: pinhole-camera distance estimate.
- `_distance_color()`: proximity gauge color.
- `DistanceTracker`: smooths detections using centroid matching and a rolling median.
- `load_authorized_faces()`: loads whitelist image templates.
- `is_authorized()`: compares a detected face crop with whitelist templates.
- `send_telegram()`: sends a snapshot and GPS location through the Telegram Bot API.
- `CameraThread.run()`: captures frames, runs YOLO, applies threat rules, records evidence, and updates the stream frame.
- `main()`: loads the model, starts camera threads, and serves `/video_feed` on port 5001.

### `demo.py`

- `_load_config()`: reads distance settings.
- `_get_best_weights()`: selects the first available model.
- `_estimate_distance()`: estimates distance for offline detections.
- `_video_worker()`: runs the frame-by-frame OpenCV/YOLO analysis.
- `run_video()`: opens the file picker and starts the worker.
- `run_live()`: starts `livedetector.py` from the legacy standalone UI.
- `open_folder()`, `open_training_graphs()`, `open_config()`: open project assets.
- `_build_ui()`: builds the older standalone Tkinter interface.

## Optional Training and Legacy Files

None of the following files are required to open or operate the normal `netra_app.py` GUI. They are development utilities or an older web interface:

| File/path | Purpose |
| --- | --- |
| `train.py` | Basic custom YOLO training using a local `data.yaml`. |
| `auto_setup.py` | Optional COCO128/Kaggle setup and training workflow. |
| `video_to_dataset.py` | Auto-labels videos/raw frames and merges generated data into the border dataset. |
| `dataset/` | Local custom training data and labels. |
| `datasets/` | Downloaded or generated datasets. |
| `custom_videos/` | Input videos for `video_to_dataset.py`. |
| `runs/detect/border_surveillance/sih26187_final/weights/best.pt` | Published custom model used first by Live Surveillance and offline analysis. |
| `yolov8n.pt` | Small fallback/pretrained YOLO model used if the custom model is unavailable. |
| `weights/yolo26n.pt` | Additional weight file present in the workspace; it is not selected by the current detector search paths. |
| `runs/` | Ultralytics training outputs, checkpoints, and metrics. |

The local workspace also contains `prepare_dataset.py` and `train_gpu.py`. They are intentionally left out of the GitHub publish set because the application does not import or call them. Keep them locally only if you plan to prepare a custom dataset or run GPU training.

`app_backup.py` and `index4.html` belong to an older Flask/web dashboard path. The current application is the desktop `netra_app.py` interface, so these legacy files are also excluded from the focused publish set. `Dockerfile` and `docker-compose.yml` support the separate training workflow rather than normal desktop execution.

Training output is not automatically used unless it is saved at one of the detector's searched paths.

## Docker Training Files

- `Dockerfile` builds a Python 3.11 training image with Ultralytics and Kaggle support.
- `docker-compose.yml` runs the `trainer` service with optional NVIDIA GPU access and persistent dataset/output volumes.
- Docker training is separate from the Windows CustomTkinter GUI. It does not replace the local GUI runtime setup.

The Dockerfile expects a `kaggle.json` credential file, but that file is not listed in the current workspace tree. Do not add credentials to a public repository.

## Troubleshooting

### The GUI does not open

Check that the command is being run in a desktop session and that CustomTkinter/Pillow are installed:

```powershell
python -c "import customtkinter, PIL; print('GUI dependencies OK')"
```

### Live feed shows connecting or the detector exits

- Check the camera index or RTSP URL in `config.json`.
- Run `python livedetector.py` directly and read its console output.
- Confirm port `5001` is free.
- Confirm a model file exists and that `ultralytics` and `torch` import successfully.

### No Telegram alert arrives

- Set both `telegram.bot_token` and `telegram.chat_id`.
- Verify the bot can message the target chat.
- Check internet connectivity and the detector console output.

### No training graph data appears

This is expected when no matching `results.csv` exists. The page will use its built-in fallback arrays. Run training or place the results CSV at one of the paths documented above.

## GitHub Publishing

The repository contains source code, documentation, configuration with blank secrets, the custom `best.pt` model, and the `yolov8n.pt` fallback model. The `.gitignore` intentionally excludes:

- `.venv/`, `.venv312/`, Python caches, and local editor/build files.
- `alerts/` evidence recordings and `authorized/` personal face images.
- `custom_videos/` private footage.
- `dataset/`, `datasets/`, most `runs/` output, and generated training weights. The intended custom model at `runs/detect/border_surveillance/sih26187_final/weights/best.pt` is explicitly included.
- `kaggle.json`, `.env` files, and other local credentials.

Before publishing, confirm that `config.json` still contains empty Telegram credentials and that no private media or credentials are staged. A fresh clone will need to recreate the ignored folders and install dependencies before running the app.

## Current Limitations

- The GUI is Windows-oriented because it uses `os.startfile` and a Windows `.venv312` path when available.
- The Live camera dropdown does not currently control which configured camera is processed.
- Offline analysis opens an OpenCV popup; results are not rendered as individual detections inside the GUI.
- Live and offline detection use different class registries, so custom model class ordering should be checked before deployment.
- Distance values are estimates and require camera-specific calibration.
- This system is a prototype and should not be treated as the sole safety or security control.