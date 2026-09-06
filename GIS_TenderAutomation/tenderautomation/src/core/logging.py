import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

SENSITIVE_KEYS = frozenset(
    {"password", "token", "cookie", "secret", "auth", "credential", "key"}
)


class JsonFormatter(logging.Formatter):
    def _sanitize(self, obj: dict[str, Any]) -> dict[str, Any]:
        return {
            k: "***" if any(s in k.lower() for s in SENSITIVE_KEYS) else v
            for k, v in obj.items()
        }

    def format(self, record: logging.LogRecord) -> str:
        context = self._sanitize(getattr(record, "context", {}))
        entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if context:
            entry["context"] = context
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger
