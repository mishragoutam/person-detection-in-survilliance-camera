"""Evidence file and metadata handling."""

from __future__ import annotations

import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any


class EvidenceManager:
    """Create bounded, date-organized event evidence directories."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def event_directory(self, event_id: str | None = None) -> Path:
        event_id = event_id or uuid.uuid4().hex
        folder = self.root / date.today().isoformat() / event_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def write_metadata(self, event: dict[str, Any], folder: str | Path) -> Path:
        path = Path(folder) / "metadata.json"
        path.write_text(json.dumps(event, indent=2, default=str), encoding="utf-8")
        return path
