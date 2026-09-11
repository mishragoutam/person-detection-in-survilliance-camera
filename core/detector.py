import logging
from pathlib import Path
from typing import List, Tuple
from ultralytics import YOLO

logger = logging.getLogger("netra.detector")

class Detector:
    def __init__(self, confidence: float):
        self.confidence = confidence
        self.models = []
        self._load_models()

    def _load_models(self):
        project_dir = Path(__file__).resolve().parent.parent
        custom_weights = project_dir / "runs" / "detect" / "border_surveillance" / "sih26187_final" / "weights" / "best.pt"
        if not custom_weights.exists():
            custom_weights = project_dir / "yolov8n.pt"
        coco_weights = project_dir / "yolov8n.pt"

        if not custom_weights.exists():
            logger.error("No YOLO checkpoint found at %s", custom_weights)
            return
            
        logger.info("Loading custom checkpoint: %s", custom_weights)
        try:
            custom_model = YOLO(str(custom_weights))
            self.models.append((custom_model, list(custom_model.names.keys()), 0))
        except Exception:
            logger.exception("Failed to load custom checkpoint: %s", custom_weights)
            return

        if coco_weights.exists() and coco_weights.resolve() != custom_weights.resolve():
            logger.info("Loading COCO checkpoint: %s", coco_weights)
            try:
                coco_wanted_classes = [0, 2, 3, 5, 7]
                self.models.append((YOLO(str(coco_weights)), coco_wanted_classes, 1))
            except Exception:
                logger.exception("Failed to load COCO checkpoint: %s", coco_weights)

    def _box_iou(self, left: Tuple[int, int, int, int], right: Tuple[int, int, int, int]) -> float:
        lx1, ly1, lx2, ly2 = left
        rx1, ry1, rx2, ry2 = right
        ix1, iy1 = max(lx1, rx1), max(ly1, ry1)
        ix2, iy2 = min(lx2, rx2), min(ly2, ry2)
        intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        left_area = max(0, lx2 - lx1) * max(0, ly2 - ly1)
        right_area = max(0, rx2 - rx1) * max(0, ry2 - ry1)
        union = left_area + right_area - intersection
        return intersection / union if union else 0.0

    def detect(self, frame) -> List[Tuple[int, float, str, int, int, int, int, int]]:
        """Run both models on one frame and remove overlapping duplicates."""
        detections = []
        for model, classes, source_priority in self.models:
            results = model(frame, classes=classes, conf=self.confidence,
                            imgsz=640, max_det=20, verbose=False)
            for box in results[0].boxes:
                raw_id = int(box.cls[0])
                raw_name = str(model.names.get(raw_id, "object")).lower()
                if raw_name in {"person", "pedestrian", "people"}:
                    cls_id, name = 1, "Person"
                elif raw_name == "fence":
                    cls_id, name = 0, "Fence"
                elif raw_name == "face":
                    cls_id, name = 2, "Face"
                elif raw_name in {"car", "motorcycle", "bus", "truck", "vehicle"}:
                    cls_id, name = 3, raw_name.title()
                else:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                detections.append((source_priority, cls_id, float(box.conf[0]), name,
                                   x1, y1, x2, y2, max(0, y2 - y1)))

        detections.sort(key=lambda item: (item[1], item[0], -item[2]))
        merged = []
        for src, cls_id, conf, name, x1, y1, x2, y2, bbox_h in detections:
            if any(
                cls_id == previous[0]
                and self._box_iou((x1, y1, x2, y2), previous[3:7]) >= 0.50
                for previous in merged
            ):
                continue
            merged.append((cls_id, conf, name, x1, y1, x2, y2, bbox_h))
        return merged
