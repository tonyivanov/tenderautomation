"""Title dedup + cache keys."""
from __future__ import annotations

import hashlib

from . import config


def light_normalize(title: str) -> str:
    """Minimal normalization for dedup only — lowercase + collapse spaces."""
    return " ".join(title.lower().split())


SCHEMA_VERSION = "v3.2"
AGGREGATION_VERSION = "v3.2.3.1"

def make_cache_key(title: str) -> str:
    normal = light_normalize(title)
    raw = f"{normal}|{config.PROMPT_VERSION}|{SCHEMA_VERSION}|{AGGREGATION_VERSION}|{config.OPENROUTER_MODEL_PRIMARY}"
    return hashlib.sha256(raw.encode()).hexdigest()
