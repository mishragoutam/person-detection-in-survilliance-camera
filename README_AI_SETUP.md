# NETRA AI Setup Guide

This guide helps a new user install and run NETRA after downloading the repository.
NETRA is a Windows desktop application and requires a graphical desktop session.
The custom trained YOLO model is already included at:

`runs/detect/border_surveillance/sih26187_final/weights/best.pt`

## Copy-Paste Prompt For An AI Assistant

Copy the prompt below into ChatGPT, GitHub Copilot, or another coding assistant while your terminal is open in the repository folder:

```text
I downloaded this Windows Python project and want to run NETRA, whose entry point is netra_app.py.

Please help me set it up safely and verify it works:
1. Inspect requirements.txt and the Python version available on this computer.
2. Create a local virtual environment named .venv using Python 3.11 or 3.12 if available.
3. Activate .venv, upgrade pip inside that environment, and install all packages from requirements.txt.
4. Do not install packages globally, delete project files, change config.json automatically, or expose any Telegram credentials.
5. Confirm that the custom model exists at runs/detect/border_surveillance/sih26187_final/weights/best.pt.
6. Run a syntax check for netra_app.py, livedetector.py, and demo.py.
7. Start the application with python netra_app.py.
8. If an installation or runtime error occurs, show the exact error and suggest the smallest fix. Ask for confirmation before making any unrelated changes.
```

## Direct Windows Setup

Open PowerShell in the repository folder and run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m py_compile netra_app.py livedetector.py demo.py
python netra_app.py
```

If Python 3.12 is unavailable, use Python 3.11:

```powershell
py -3.11 -m venv .venv
```

If PowerShell blocks environment activation, run the environment interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe netra_app.py
```

## First Run Notes

- Windows must have a working desktop display because NETRA uses Tkinter and CustomTkinter.
- A webcam, RTSP stream, or video file is needed for detection operations.
- Review `config.json` and set camera or Telegram values yourself. Leave Telegram fields blank to disable notifications.
- Alert images and recordings are written to `alerts/`; authorized-person images belong in `authorized/`.
- CCTV files selected for analysis belong in `custom_videos/`, but are intentionally not published to Git.
- CPU inference works, but an NVIDIA GPU can improve detection speed.