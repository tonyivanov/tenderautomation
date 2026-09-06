from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.models import TenderModel
from core.logging import get_logger

log = get_logger(__name__)


class QualifiedLogRepository:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    def _current_path(self) -> Path:
        month = datetime.now(timezone.utc).strftime("%Y-%m")
        path = self._data_dir / f"tenders_{month}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def all_paths(self) -> list[Path]:
        return sorted(self._data_dir.glob("tenders_*.jsonl"))

    def append_batch(self, tenders: list[TenderModel]) -> None:
        if not tenders:
            return
        path = self._current_path()
        with open(path, "a", encoding="utf-8") as f:
            for tender in tenders:
                line = json.dumps(tender.to_jsonl_dict(), ensure_ascii=False)
                f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        log.info(
            "jsonl_batch_written",
            extra={"context": {"file": str(path), "count": len(tenders)}},
        )

    def read_since(self, since: datetime) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for path in self.all_paths():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        exported_at_str = record.get("exported_at", "")
                        if exported_at_str:
                            exported_at = datetime.fromisoformat(exported_at_str)
                            if exported_at >= since:
                                results.append(record)
                    except (json.JSONDecodeError, ValueError):
                        continue
        return results
