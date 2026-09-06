from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.models import TenderAction
from core.logging import get_logger

log = get_logger(__name__)


class ActionLogRepository:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def _current_path(self) -> Path:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        path = self._data_dir / f"actions_{month}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def append(self, action: TenderAction) -> None:
        path = self._current_path()
        with open(path, "a", encoding="utf-8") as f:
            line = json.dumps(action.to_jsonl_dict(), ensure_ascii=False)
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())

    def read_all(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for path in sorted(self._data_dir.glob("actions_*.jsonl")):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            results.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return results
