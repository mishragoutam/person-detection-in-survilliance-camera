import os
from pathlib import Path
import sys
import torch
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Dataset
from torch.cuda.amp import autocast, GradScaler
import torch.nn as nn
import torch.optim as optim
from ultralytics import YOLO
import cv2

# Configuration for RTX 3050 4GB/6GB
BATCH_SIZE = 8
EPOCHS = 20
IMG_SIZE = 640
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
AMP_ENABLED = True  # Automatic Mixed Precision to save VRAM

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR    = PROJECT_DIR / "dataset"
RUNS_DIR    = PROJECT_DIR / "hybrid_model_runs"

def check_dataset():
    """Verify that youtube_labeler.py has already populated the dataset directory."""
    yaml_path  = DATA_DIR / "data.yaml"
    train_imgs = DATA_DIR / "images" / "train"
    has_images = train_imgs.exists() and any(train_imgs.iterdir())

    if not has_images or not yaml_path.exists():
        print(
            "\n[ERROR] Dataset not found or empty."
            f"\n  Expected: {DATA_DIR / 'images' / 'train'}  (images)"
            f"\n  Expected: {yaml_path}  (data.yaml)"
            "\n"
            "\n  Please run the YouTube labeler first to build the dataset:"
            "\n    python scripts/youtube_labeler.py --urls \"<YouTube URL>\""
            "\n"
        )
        sys.exit(1)

    n_train = len(list(train_imgs.glob("*.jpg"))) + len(list(train_imgs.glob("*.png")))
    print(f"Dataset ready: {n_train} training images found in {train_imgs}")

def train_yolo():
    print("Starting YOLOv8n Training...")
    # Assuming dataset has a data.yaml after extraction, adjust path if needed
    yaml_path = DATA_DIR / "data.yaml"
    if not yaml_path.exists():
        # Fallback if the dataset structure is different, we might need to create it.
        # Searching for yaml
        yamls = list(DATA_DIR.rglob("*.yaml"))
        if yamls:
            yaml_path = yamls[0]
        else:
            print("Warning: data.yaml not found. You might need to configure the dataset path manually.")
            return None

    run_dir = RUNS_DIR / "yolov8n_person_det"
    last_checkpoint = run_dir / "weights" / "last.pt"
    if last_checkpoint.exists():
        print(f"Resuming YOLO training from {last_checkpoint}")
        model = YOLO(str(last_checkpoint))
        resume = True
    else:
        model = YOLO(str(PROJECT_DIR / "yolov8n.pt"))
        resume = False
    
    # Train with RTX 3050 optimizations
    results = model.train(
        data=str(yaml_path),
        epochs=EPOCHS,
        imgsz=IMG_SIZE,
        batch=BATCH_SIZE,
        device=0 if torch.cuda.is_available() else 'cpu',
        amp=AMP_ENABLED,  # Half precision
        workers=2,        # Keep CPU workers low to prevent RAM starvation
        project=str(RUNS_DIR),
        name="yolov8n_person_det",
        resume=resume,
    )
    return results

class CropDataset(Dataset):
    """Dataset to load crops for ResNet18 training"""
    def __init__(self, data_dir, transform=None):
        self.data_dir = Path(data_dir)
        self.transform = transform
        self.samples = [] # List of (image_path, label)
        # Simplified: we assume we have folders 'person' and 'background' or we parse labels.
        # Since it's a YOLO dataset, we parse labels.txt
        images = list(self.data_dir.rglob("*.jpg")) + list(self.data_dir.rglob("*.png"))
        for img_path in images:
            label_path = img_path.with_suffix('.txt')
            if label_path.exists():
                with open(label_path, 'r') as f:
                    lines = f.readlines()
                    for line in lines:
                        self.samples.append((img_path, line.strip()))
    
    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, label_str = self.samples[idx]
        img = cv2.imread(str(img_path))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Parse YOLO label: class x_center y_center width height (normalized)
        parts = label_str.split()
        cls_id = int(parts[0])
        x_c, y_c, w, h = map(float, parts[1:5])
        
        H, W, _ = img.shape
        x1 = int((x_c - w/2) * W)
        y1 = int((y_c - h/2) * H)
        x2 = int((x_c + w/2) * W)
        y2 = int((y_c + h/2) * H)
        
        # Add padding/bound checks
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W, x2), min(H, y2)
        
        if x2 <= x1 or y2 <= y1:
            crop = torch.zeros((3, 224, 224))
        else:
            crop = img[y1:y2, x1:x2]
            if self.transform:
                try:
                    from PIL import Image
                    crop_pil = Image.fromarray(crop)
                    crop = self.transform(crop_pil)
                except Exception:
                    crop = torch.zeros((3, 224, 224))
            else:
                crop = torch.zeros((3, 224, 224))
                
        return crop, cls_id

def train_resnet():
    print("Starting ResNet18 Training on Crops...")
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    dataset = CropDataset(DATA_DIR, transform=transform)
    if len(dataset) == 0:
        print("No labels found for ResNet18 crop training.")
        return
        
    loader = DataLoader(dataset, batch_size=BATCH_SIZE*2, shuffle=True, num_workers=2)
    
    # Get number of classes from data.yaml if it exists
    num_classes = 2
    yaml_path = DATA_DIR / "data.yaml"
    if yaml_path.exists():
        import yaml
        with open(yaml_path, 'r') as f:
            data = yaml.safe_load(f)
            num_classes = data.get("nc", 2)

    model = torchvision.models.resnet18(weights=torchvision.models.ResNet18_Weights.DEFAULT)
    num_ftrs = model.fc.in_features
    model.fc = nn.Linear(num_ftrs, num_classes)
    model = model.to(DEVICE)
    
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(model.parameters(), lr=1e-4)
    scaler = GradScaler(enabled=AMP_ENABLED)
    
    model.train()
    for epoch in range(EPOCHS):
        running_loss = 0.0
        for inputs, labels in loader:
            inputs, labels = inputs.to(DEVICE), labels.to(DEVICE)
            
            optimizer.zero_grad()
            with autocast(enabled=AMP_ENABLED):
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            
            running_loss += loss.item()
            
        print(f"Epoch {epoch+1}/{EPOCHS} - ResNet Loss: {running_loss/len(loader):.4f}")
        
    models_dir = PROJECT_DIR / "scripts" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), models_dir / "resnet18_hybrid.pth")
    print(f"ResNet18 training complete. Saved to {models_dir / 'resnet18_hybrid.pth'}")

if __name__ == "__main__":
    check_dataset()
    train_yolo()
    train_resnet()
    print("Hybrid Training Pipeline Completed Successfully.")
