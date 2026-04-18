from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class HistoryStore:
    def __init__(self, history_dir: str):
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save(self, data: dict[str, Any]) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"banner_{timestamp}.json"
        file_path = self.history_dir / filename
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return filename

    def list_files(self, limit: int = 50) -> list[dict[str, Any]]:
        files = sorted(self.history_dir.glob("banner_*.json"), reverse=True)
        entries: list[dict[str, Any]] = []
        for file_path in files[:limit]:
            entries.append(
                {
                    "file": file_path.name,
                    "created_at": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                    "size": file_path.stat().st_size,
                }
            )
        return entries

    def load(self, filename: str) -> dict[str, Any]:
        file_path = self.history_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(filename)
        return json.loads(file_path.read_text(encoding="utf-8"))
