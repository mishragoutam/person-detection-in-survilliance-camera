#!/usr/bin/env python3
"""
YouTube Video Auto-Labeler for Person Detection Dataset
=======================================================
Downloads YouTube videos, extracts frames, auto-labels them using
YOLOv8n + ResNet18, and merges labeled data into the training dataset.

Usage:
    python scripts/youtube_labeler.py --urls "URL1" "URL2" [options]
    python scripts/youtube_labeler.py --url-file urls.txt [options]

Examples:
    # Label a single video
    python scripts/youtube_labeler.py --urls "https://www.youtube.com/watch?v=XXXX"

    # Label multiple videos with custom settings
    python scripts/youtube_labeler.py \
        --urls "https://youtube.com/watch?v=A" "https://youtube.com/watch?v=B" \
        --fps 1 \
        --conf 0.55 \
        --val-split 0.2 \
        --max-frames 2000
"""

import argparse
import hashlib
import logging
import os
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch
import torchvision
import torchvision.transforms as T
import yaml
from tqdm import tqdm
from ultralytics import YOLO

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_DIR    = Path(__file__).resolve().parent.parent
DATASET_DIR    = PROJECT_DIR / "dataset"
MODELS_DIR     = PROJECT_DIR / "scripts" / "models"
DOWNLOADS_DIR  = PROJECT_DIR / "scripts" / "_yt_downloads"

YOLO_WEIGHTS   = PROJECT_DIR / "yolov8n.pt"
RESNET_WEIGHTS = MODELS_DIR / "resnet18_hybrid.pth"

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("yt_labeler")

# ── Target Classes ─────────────────────────────────────────────────────────────
# We define a mapping of class names to output IDs for the dataset.
# If you have a custom YOLO model, it might output these directly.
DATASET_NAMES = {
    0: "person",
    1: "face",
    2: "car",
}

# Inverse mapping for YOLO detection (assuming standard COCO or custom model)
# You can customize which YOLO classes map to which dataset classes.
YOLO_TO_DATASET_CLASS = {
    0: 0,  # YOLO 'person' -> Dataset 'person'
    1: 1,  # YOLO 'face' (if custom) -> Dataset 'face'
    2: 2,  # YOLO 'car' -> Dataset 'car'
}


# ══════════════════════════════════════════════════════════════════════════════
# Model loading
# ══════════════════════════════════════════════════════════════════════════════

def load_yolo(weights_path: Path) -> YOLO:
    if not weights_path.exists():
        log.info("YOLOv8n weights not found locally – downloading yolov8n.pt …")
    model = YOLO(str(weights_path))
    log.info(f"Loaded YOLO: {weights_path.name}")
    return model


def load_resnet(device: torch.device) -> Optional[torch.nn.Module]:
    """Load custom ResNet18 if available, else fall back to ImageNet pretrained."""
    model = torchvision.models.resnet18(
        weights=torchvision.models.ResNet18_Weights.DEFAULT
    )
    if RESNET_WEIGHTS.exists():
        try:
            num_ftrs = model.fc.in_features
            model.fc = torch.nn.Linear(num_ftrs, 2)
            state = torch.load(RESNET_WEIGHTS, map_location=device)
            model.load_state_dict(state)
            log.info(f"Loaded custom ResNet18 from {RESNET_WEIGHTS.name}")
        except Exception as e:
            log.warning(f"Could not load custom ResNet18 ({e}). Falling back to ImageNet.")
            model = torchvision.models.resnet18(
                weights=torchvision.models.ResNet18_Weights.DEFAULT
            )
    else:
        log.info("Custom ResNet18 not trained yet – using ImageNet weights for validation.")

    model = model.to(device).eval()
    return model


# ══════════════════════════════════════════════════════════════════════════════
# YouTube download
# ══════════════════════════════════════════════════════════════════════════════

def download_video(url: str, out_dir: Path) -> Optional[Path]:
    """Download a YouTube video to out_dir using yt-dlp.
    Returns the path to the downloaded video file, or None on failure."""
    out_dir.mkdir(parents=True, exist_ok=True)
    # Use a hash of the URL as the filename to avoid duplicates / long names
    url_hash = hashlib.md5(url.encode()).hexdigest()[:10]
    out_template = str(out_dir / f"{url_hash}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",           # Only download the single video, not a playlist
        "--format", "bestvideo[height<=720][ext=mp4]/best[height<=720][ext=mp4]/best",
        "--output", out_template,
        "--quiet",
        "--no-warnings",
        url,
    ]
    log.info(f"Downloading: {url}")
    try:
        subprocess.run(cmd, check=True, timeout=600)
        # Find the file yt-dlp wrote
        matches = list(out_dir.glob(f"{url_hash}.*"))
        if not matches:
            log.error("yt-dlp ran but no file was found.")
            return None
        video_path = matches[0]
        size_mb = video_path.stat().st_size / 1_048_576
        log.info(f"Downloaded → {video_path.name}  ({size_mb:.1f} MB)")
        return video_path
    except subprocess.CalledProcessError as e:
        log.error(f"yt-dlp failed for {url}: {e}")
        return None
    except subprocess.TimeoutExpired:
        log.error(f"Download timed out for {url}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Frame extraction with scene-change deduplication
# ══════════════════════════════════════════════════════════════════════════════

def extract_frames(
    video_path: Path,
    fps: float = 1.0,
    max_frames: int = 0,
    scene_thresh: float = 25.0,
) -> List[np.ndarray]:
    """Extract frames from a video.

    Args:
        video_path:   Path to the video file.
        fps:          How many frames to extract per second of video.
        max_frames:   Hard cap on number of frames (0 = no cap).
        scene_thresh: Minimum mean-absolute-diff between consecutive sampled
                      frames to keep the frame (deduplication).  Lower = stricter.
    """
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        log.error(f"Cannot open video: {video_path}")
        return []

    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s = total_frames / video_fps
    sample_interval = max(1, int(round(video_fps / fps)))

    log.info(
        f"Video: {video_path.name}  |  {duration_s:.1f}s  |  "
        f"source {video_fps:.1f}fps  |  sampling every {sample_interval} frames"
    )

    frames: List[np.ndarray] = []
    prev_gray: Optional[np.ndarray] = None
    frame_idx = 0

    with tqdm(total=total_frames, desc="Extracting frames", unit="frm") as pbar:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            pbar.update(1)

            if frame_idx % sample_interval != 0:
                frame_idx += 1
                continue

            # Scene-change deduplication
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None:
                diff = float(np.mean(np.abs(gray.astype(np.float32) - prev_gray.astype(np.float32))))
                if diff < scene_thresh:
                    frame_idx += 1
                    continue
            prev_gray = gray
            frames.append(frame.copy())

            if max_frames and len(frames) >= max_frames:
                log.info(f"Reached max_frames cap ({max_frames}). Stopping extraction.")
                break
            frame_idx += 1

    cap.release()
    log.info(f"Extracted {len(frames)} unique frames.")
    return frames


# ══════════════════════════════════════════════════════════════════════════════
# Auto-labeling (YOLO + optional ResNet18 confirmation)
# ══════════════════════════════════════════════════════════════════════════════

_RESNET_TRANSFORM = T.Compose([
    T.ToPILImage(),
    T.Resize((224, 224)),
    T.ToTensor(),
    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])


def _resnet_is_person(
    crop_bgr: np.ndarray,
    resnet: torch.nn.Module,
    device: torch.device,
    threshold: float = 0.5,
    is_custom: bool = False,
) -> bool:
    """Return True if ResNet18 thinks the crop is a person."""
    crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
    tensor = _RESNET_TRANSFORM(crop_rgb).unsqueeze(0).to(device)
    with torch.no_grad():
        out = resnet(tensor)
    if is_custom:
        # 2-class output: [background, person]
        probs = torch.nn.functional.softmax(out, dim=1)
        return probs[0][1].item() >= threshold
    else:
        # ImageNet pretrained: classes 0-14 ≈ person-like + class 879 = person
        # We accept any activation in person-related range
        pred = int(torch.argmax(out, dim=1).item())
        # ImageNet: people classes are roughly 0-14 and 879 (basketball player, etc.)
        person_imagenet_ids = set(range(15)) | {879}
        return pred in person_imagenet_ids


def label_frames(
    frames: List[np.ndarray],
    yolo: YOLO,
    resnet: torch.nn.Module,
    device: torch.device,
    conf_threshold: float = 0.45,
    ensemble_mode: str = "and",
    resnet_is_custom: bool = False,
    min_labels: int = 1,
    max_labels: int = 0,
) -> List[Tuple[np.ndarray, List[str]]]:
    """
    Run YOLO on each frame, validate crops with ResNet18 based on ensemble_mode.
    
    ensemble_mode options:
      'and'         : Both YOLO and ResNet must agree (YOLO class matches AND ResNet says yes).
      'or'          : Keep if either YOLO class matches OR ResNet says yes.
      'yolo_only'   : Only rely on YOLO detections.
      'resnet_only' : Evaluate all YOLO box proposals using ResNet only.
      
    Returns:
        List of (frame_bgr, yolo_label_lines) for frames that pass the label count filters.
    """
    labeled: List[Tuple[np.ndarray, List[str]]] = []

    log.info(f"Labeling {len(frames)} frames (YOLO conf≥{conf_threshold}) …")
    for frame in tqdm(frames, desc="Labeling", unit="frame"):
        H, W = frame.shape[:2]
        # In 'resnet_only' or 'or' mode, we might want to evaluate all proposals, 
        # so we don't strictly filter classes in YOLO. For simplicity, we can let YOLO 
        # output all its detected classes or just use the ones in YOLO_TO_DATASET_CLASS.
        # If we want ResNet to evaluate *any* object, we shouldn't restrict classes here.
        classes_to_detect = list(YOLO_TO_DATASET_CLASS.keys()) if ensemble_mode in ["and", "yolo_only"] else None
        
        results = yolo(frame, classes=classes_to_detect,
                       conf=conf_threshold, imgsz=640, verbose=False)

        label_lines: List[str] = []
        for box in results[0].boxes:
            yolo_cls_id = int(box.cls[0])
            yolo_says_target = yolo_cls_id in YOLO_TO_DATASET_CLASS
            
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(W, x2), min(H, y2)
            if x2 <= x1 or y2 <= y1:
                continue

            # Check ResNet prediction if required by the mode
            resnet_says_person = False
            if ensemble_mode in ["and", "or", "resnet_only"] and resnet is not None:
                crop = frame[y1:y2, x1:x2]
                if crop.size > 0:
                    try:
                        resnet_says_person = _resnet_is_person(crop, resnet, device, is_custom=resnet_is_custom)
                    except Exception:
                        pass # ResNet failed, assume False

            # Determine if we keep the detection based on ensemble_mode
            keep = False
            out_class_id = 0 # Default to person (0)
            
            if ensemble_mode == "yolo_only":
                if yolo_says_target:
                    keep = True
                    out_class_id = YOLO_TO_DATASET_CLASS[yolo_cls_id]
            elif ensemble_mode == "resnet_only":
                if resnet_says_person:
                    keep = True
                    out_class_id = 0 # ResNet predicts person
            elif ensemble_mode == "and":
                if yolo_says_target and resnet_says_person:
                    keep = True
                    out_class_id = YOLO_TO_DATASET_CLASS[yolo_cls_id]
            elif ensemble_mode == "or":
                if yolo_says_target or resnet_says_person:
                    keep = True
                    # Prefer YOLO's specific class if it matched, else default to person (0)
                    out_class_id = YOLO_TO_DATASET_CLASS[yolo_cls_id] if yolo_says_target else 0

            if not keep:
                continue

            x_c = ((x1 + x2) / 2) / W
            y_c = ((y1 + y2) / 2) / H
            bw  = (x2 - x1) / W
            bh  = (y2 - y1) / H
            label_lines.append(f"{out_class_id} {x_c:.6f} {y_c:.6f} {bw:.6f} {bh:.6f}")

        # Check label count constraints
        num_labels = len(label_lines)
        if num_labels >= min_labels and (max_labels == 0 or num_labels <= max_labels):
            labeled.append((frame, label_lines))

    log.info(f"Frames with valid detections: {len(labeled)} / {len(frames)}")
    return labeled


# ══════════════════════════════════════════════════════════════════════════════
# Dataset management
# ══════════════════════════════════════════════════════════════════════════════

def ensure_dataset_structure(dataset_dir: Path) -> Tuple[Path, Path, Path, Path]:
    """Create train/val split directories and return their paths."""
    for split in ("train", "val"):
        (dataset_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (dataset_dir / "labels" / split).mkdir(parents=True, exist_ok=True)
    return (
        dataset_dir / "images" / "train",
        dataset_dir / "images" / "val",
        dataset_dir / "labels" / "train",
        dataset_dir / "labels" / "val",
    )


def save_to_dataset(
    labeled: List[Tuple[np.ndarray, List[str]]],
    dataset_dir: Path,
    val_split: float = 0.2,
    prefix: str = "yt",
) -> Tuple[int, int]:
    """
    Save labeled frames into the dataset directory.
    Images go to  dataset/images/{train|val}/
    Labels go to  dataset/labels/{train|val}/

    Returns:
        (n_train, n_val) count of saved samples.
    """
    img_train, img_val, lbl_train, lbl_val = ensure_dataset_structure(dataset_dir)

    random.shuffle(labeled)
    n_val = max(1, int(len(labeled) * val_split))
    val_set   = set(range(len(labeled) - n_val, len(labeled)))
    n_train_saved = n_val_saved = 0

    for idx, (frame, lines) in enumerate(tqdm(labeled, desc="Saving to dataset", unit="img")):
        # Unique filename based on frame content hash
        frame_hash = hashlib.md5(frame.tobytes()).hexdigest()[:12]
        fname = f"{prefix}_{frame_hash}"

        if idx in val_set:
            img_out = img_val / f"{fname}.jpg"
            lbl_out = lbl_val / f"{fname}.txt"
            n_val_saved += 1
        else:
            img_out = img_train / f"{fname}.jpg"
            lbl_out = lbl_train / f"{fname}.txt"
            n_train_saved += 1

        cv2.imwrite(str(img_out), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
        lbl_out.write_text("\n".join(lines))

    return n_train_saved, n_val_saved


def update_data_yaml(dataset_dir: Path) -> Path:
    """Create or update data.yaml so train_hybrid.py can find the dataset."""
    yaml_path = dataset_dir / "data.yaml"
    data = {
        "path": str(dataset_dir.resolve()),
        "train": "images/train",
        "val":   "images/val",
        "nc":    len(DATASET_NAMES),
        "names": DATASET_NAMES,
    }

    if yaml_path.exists():
        with open(yaml_path) as f:
            existing = yaml.safe_load(f) or {}
        # Merge names – existing names are kept, ours are added
        existing_names = existing.get("names", {})
        if isinstance(existing_names, list):
            existing_names = {i: n for i, n in enumerate(existing_names)}
        merged_names = {**existing_names, **DATASET_NAMES}
        data["names"] = merged_names
        data["nc"]    = len(merged_names)

    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    log.info(f"data.yaml updated → {yaml_path}")
    return yaml_path


# ══════════════════════════════════════════════════════════════════════════════
# Main pipeline
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(
    sources: List[str],
    fps: float = 1.0,
    conf: float = 0.45,
    max_frames: int = 0,
    val_split: float = 0.2,
    ensemble_mode: str = "and",
    min_labels: int = 1,
    max_labels: int = 2,
    keep_videos: bool = False,
    scene_thresh: float = 25.0,
    gpu: int = 0,
):
    device = torch.device(f"cuda:{gpu}" if torch.cuda.is_available() else "cpu")
    log.info(f"Device: {device}")

    # Load models
    yolo   = load_yolo(YOLO_WEIGHTS)
    
    # We only need ResNet if ensemble mode requires it
    use_resnet = ensemble_mode in ["and", "or", "resnet_only"]
    resnet = load_resnet(device) if use_resnet else None
    resnet_is_custom = RESNET_WEIGHTS.exists()

    total_train = total_val = 0

    for source in sources:
        log.info(f"\n{'='*60}")
        log.info(f"Processing: {source}")
        log.info(f"{'='*60}")

        is_local = os.path.exists(source)

        # 1. Download or use local file
        if is_local:
            video_path = Path(source)
            log.info(f"Using local video file: {video_path}")
        else:
            video_path = download_video(source, DOWNLOADS_DIR)
            
        if video_path is None:
            log.warning(f"Skipping {source} – download/load failed.")
            continue

        # 2. Extract frames
        frames = extract_frames(
            video_path,
            fps=fps,
            max_frames=max_frames,
            scene_thresh=scene_thresh,
        )
        if not frames:
            log.warning("No frames extracted. Skipping.")
            if not keep_videos:
                video_path.unlink(missing_ok=True)
            continue

        # 3. Auto-label
        labeled = label_frames(
            frames,
            yolo=yolo,
            resnet=resnet,
            device=device,
            conf_threshold=conf,
            ensemble_mode=ensemble_mode,
            resnet_is_custom=resnet_is_custom,
            min_labels=min_labels,
            max_labels=max_labels,
        )

        if not labeled:
            log.warning("No valid detections found in this video. Skipping save.")
            if not keep_videos:
                video_path.unlink(missing_ok=True)
            continue

        # 4. Save to dataset
        url_hash = hashlib.md5(source.encode()).hexdigest()[:6]
        n_train, n_val = save_to_dataset(
            labeled,
            dataset_dir=DATASET_DIR,
            val_split=val_split,
            prefix=f"yt_{url_hash}",
        )
        total_train += n_train
        total_val   += n_val
        log.info(f"Saved: {n_train} train  |  {n_val} val")

        # 5. Cleanup video
        if not is_local and not keep_videos:
            video_path.unlink(missing_ok=True)
            log.info("Downloaded video file removed (use --keep-videos to retain it).")

    # 6. Update data.yaml
    if total_train + total_val > 0:
        update_data_yaml(DATASET_DIR)
        log.info(
            f"\n✅ Pipeline complete!\n"
            f"   Total added → train: {total_train}  |  val: {total_val}\n"
            f"   Dataset directory: {DATASET_DIR}\n"
            f"   Now run:  python scripts/train_hybrid.py  to train the model."
        )
    else:
        log.warning("No data was added to the dataset.")


# ══════════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════════

def parse_args():
    p = argparse.ArgumentParser(
        description="YouTube/Video → Auto-Label → Dataset pipeline for person detection",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    src = p.add_mutually_exclusive_group(required=False)
    src.add_argument("--urls", nargs="+", metavar="URL",
                     help="One or more YouTube URLs")
    src.add_argument("--url-file", metavar="FILE",
                     help="Text file with one YouTube URL per line")
    src.add_argument("--videos", nargs="+", metavar="FILE",
                     help="One or more local video files")

    p.add_argument("--fps", type=float, default=1.0,
                   help="Frames to extract per second of video (e.g. 0.5 = 1 frame every 2s)")
    p.add_argument("--conf", type=float, default=0.45,
                   help="YOLO confidence threshold for accepting a detection")
    p.add_argument("--max-frames", type=int, default=0,
                   help="Max frames to extract per video (0 = unlimited)")
    p.add_argument("--val-split", type=float, default=0.2,
                   help="Fraction of frames to put in the validation set")
    p.add_argument("--ensemble-mode", choices=["and", "or", "yolo_only", "resnet_only"], default="and",
                   help="How to combine YOLO and ResNet predictions. 'and' requires both, 'or' requires either.")
    p.add_argument("--min-labels", type=int, default=1,
                   help="Minimum number of labels required in a frame to save it")
    p.add_argument("--max-labels", type=int, default=2,
                   help="Maximum number of labels allowed in a frame to save it (0 for unlimited)")
    p.add_argument("--keep-videos", action="store_true",
                   help="Keep downloaded videos after processing")
    p.add_argument("--scene-thresh", type=float, default=25.0,
                   help="Scene-change sensitivity (lower = keep fewer near-identical frames)")
    p.add_argument("--gpu", type=int, default=0,
                   help="GPU index to use (0 for first GPU)")

    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.url_file:
        url_file = Path(args.url_file)
        if not url_file.exists():
            log.error(f"URL file not found: {url_file}")
            sys.exit(1)
        sources = [line.strip() for line in url_file.read_text().splitlines()
                if line.strip() and not line.startswith("#")]
    elif args.videos:
        sources = args.videos
    elif args.urls:
        sources = args.urls
    else:
        input_dir = PROJECT_DIR / "input_videos"
        sources = []
        if input_dir.exists():
            for ext in ("*.mp4", "*.avi", "*.mkv", "*.mov"):
                sources.extend([str(p) for p in input_dir.glob(ext)])
        if not sources:
            log.error("No sources provided and 'input_videos' folder contains no videos.")
            sys.exit(1)

    log.info(f"Processing {len(sources)} source(s).")
    run_pipeline(
        sources=sources,
        fps=args.fps,
        conf=args.conf,
        max_frames=args.max_frames,
        val_split=args.val_split,
        ensemble_mode=args.ensemble_mode,
        min_labels=args.min_labels,
        max_labels=args.max_labels,
        keep_videos=args.keep_videos,
        scene_thresh=args.scene_thresh,
        gpu=args.gpu,
    )
