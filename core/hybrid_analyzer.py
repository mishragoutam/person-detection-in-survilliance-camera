import logging
import torch
import torchvision
import torchvision.transforms as transforms
import cv2
import numpy as np
from pathlib import Path

logger = logging.getLogger("netra.hybrid_analyzer")

class HybridAnalyzer:
    def __init__(self, device_id=0):
        self.device = torch.device(f"cuda:{device_id}" if torch.cuda.is_available() else "cpu")
        self.resnet_model = None
        self.transform = None
        self._load_resnet()

    def _load_resnet(self):
        project_dir = Path(__file__).resolve().parent.parent
        custom_resnet_path = project_dir / "scripts" / "models" / "resnet18_hybrid.pth"
        
        try:
            self.resnet_model = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.DEFAULT)
            # Check if custom model exists
            if custom_resnet_path.exists():
                logger.info(f"Loading custom ResNet18 from {custom_resnet_path}")
                
                # Fetch num_classes from data.yaml if available
                num_classes = 2
                yaml_path = project_dir / "dataset" / "data.yaml"
                if yaml_path.exists():
                    import yaml
                    with open(yaml_path, 'r') as f:
                        data = yaml.safe_load(f)
                        num_classes = data.get("nc", 2)
                        
                num_ftrs = self.resnet_model.fc.in_features
                self.resnet_model.fc = torch.nn.Linear(num_ftrs, num_classes)
                self.resnet_model.load_state_dict(torch.load(custom_resnet_path, map_location=self.device))
            else:
                logger.info("Custom ResNet18 not found. Using pretrained ImageNet weights for general feature extraction.")
            
            self.resnet_model = self.resnet_model.to(self.device)
            self.resnet_model.eval()
            
            self.transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
            ])
            logger.info("ResNet18 successfully initialized for hybrid analysis.")
        except Exception as e:
            logger.exception(f"Failed to load ResNet18: {e}")
            self.resnet_model = None

    def analyze_crops(self, frame, detections):
        """
        Takes the original frame and YOLO detections, passes crops to ResNet18.
        Detections format: [(cls_id, conf, name, x1, y1, x2, y2, bbox_h), ...]
        Returns enriched detections.
        """
        if not self.resnet_model or not self.transform:
            return detections
            
        enriched_detections = []
        for det in detections:
            cls_id, conf, name, x1, y1, x2, y2, bbox_h = det
            
            # Extract crop
            crop = frame[max(0, y1):max(0, y2), max(0, x1):max(0, x2)]
            
            if crop.size == 0:
                enriched_detections.append(det)
                continue
                
            try:
                # RGB conversion if necessary (assuming BGR from OpenCV)
                crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                input_tensor = self.transform(crop_rgb).unsqueeze(0).to(self.device)
                
                with torch.no_grad():
                    output = self.resnet_model(input_tensor)
                    
                    if getattr(self.resnet_model.fc, 'out_features', 1000) != 1000:
                        # Custom model: N-class classification
                        probabilities = torch.nn.functional.softmax(output, dim=1)
                        max_prob, predicted_idx = torch.max(probabilities, 1)
                        # We can update the name or confidence based on this
                        if max_prob.item() > 0.5:
                            # Confirm with ResNet
                            name = f"{name} (ResNet: {max_prob.item():.2f})"
                    else:
                        # ImageNet pretrained fallback
                        _, pred = torch.max(output, 1)
                        # We just keep the original detection for now, maybe add feature embeddings
                        pass 
            except Exception as e:
                logger.debug(f"Failed to analyze crop with ResNet18: {e}")
                
            enriched_detections.append((cls_id, conf, name, x1, y1, x2, y2, bbox_h))
            
        return enriched_detections
