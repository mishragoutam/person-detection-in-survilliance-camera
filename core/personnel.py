import os
import cv2
import numpy as np
from pathlib import Path
from typing import Optional, Tuple

_auth_records: list[dict] = []

def load_authorized_faces() -> None:
    """Scan authorized/ folder and build histogram templates."""
    global _auth_records
    _auth_records = []

    cascade: Optional[cv2.CascadeClassifier] = None
    try:
        cp = str(Path(__file__).resolve().parent.parent / "haarcascade_frontalface_default.xml")
        if os.path.exists(cp):
            cascade = cv2.CascadeClassifier(cp)
    except Exception:
        pass

    auth_dir = Path(__file__).resolve().parent.parent / "authorized"
    if not auth_dir.exists():
        auth_dir.mkdir(parents=True, exist_ok=True)
        
    patterns = list(auth_dir.glob("*.[jp][pn]g")) + list(auth_dir.glob("*.jpeg"))
    for img_path in patterns:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        name = img_path.stem.replace("_", " ").title()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        face_roi_color = img

        if cascade is not None:
            try:
                faces = cascade.detectMultiScale(gray, 1.1, 4, minSize=(30, 30))
                if len(faces):
                    fx, fy, fw, fh = faces[0]
                    face_roi_color = img[fy : fy + fh, fx : fx + fw]
            except Exception:
                pass

        hsv  = cv2.cvtColor(face_roi_color, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        gray_roi   = cv2.cvtColor(face_roi_color, cv2.COLOR_BGR2GRAY)
        gray_small = cv2.resize(gray_roi, (80, 80))

        _auth_records.append({"name": name, "hist": hist, "gray": gray_small})
        print(f"[AUTH] Loaded: {name}")

    print(f"[AUTH] {len(_auth_records)} authorized personnel registered.")

def is_authorized(face_crop: np.ndarray) -> Tuple[bool, str]:
    """Compare a face crop against whitelist templates. Returns (authorized, name)."""
    if not _auth_records or face_crop is None or face_crop.size == 0:
        return False, ""
    if face_crop.shape[0] < 20 or face_crop.shape[1] < 20:
        return False, ""
    try:
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
        
        cascade = None
        cp = str(Path(__file__).resolve().parent.parent / "haarcascade_frontalface_default.xml")
        if os.path.exists(cp):
            cascade = cv2.CascadeClassifier(cp)
                
        roi_color = face_crop
        if cascade is not None:
            faces = cascade.detectMultiScale(gray, 1.1, 4, minSize=(20, 20))
            if len(faces):
                fx, fy, fw, fh = faces[0]
                roi_color = face_crop[fy : fy + fh, fx : fx + fw]
                
        hsv  = cv2.cvtColor(roi_color, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        
        gray_roi = cv2.cvtColor(roi_color, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray_roi, (80, 80))

        best_score, best_name = 0.0, ""
        for rec in _auth_records:
            h_sim = float(cv2.compareHist(hist, rec["hist"], cv2.HISTCMP_CORREL))
            t_res = cv2.matchTemplate(small, rec["gray"], cv2.TM_CCOEFF_NORMED)
            t_sim = float(t_res[0][0])
            score = 0.6 * max(0.0, h_sim) + 0.4 * max(0.0, t_sim)
            if score > best_score:
                best_score, best_name = score, rec["name"]

        if best_score > 0.35:
            return True, best_name
    except Exception:
        pass
    return False, ""
