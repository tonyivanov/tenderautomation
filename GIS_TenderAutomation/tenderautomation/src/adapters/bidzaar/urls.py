from __future__ import annotations

import re
from urllib.parse import urlparse

_EXTERNAL_ID_RE = re.compile(r"^[A-Za-z0-9._~-]{1,255}$")
_CANONICAL_PREFIX = "https://bidzaar.com/app/process/light/"


def validate_external_id(value: object) -> str | None:
    candidate = str(value or "").strip()
    return candidate if _EXTERNAL_ID_RE.fullmatch(candidate) else None


def external_id_from_item(item: dict[str, object]) -> str | None:
    direct = validate_external_id(item.get("id"))
    if direct:
        return direct
    link = str(item.get("link") or "")
    try:
        suffix = urlparse(link).path.rstrip("/").rsplit("/", 1)[-1]
    except ValueError:
        return None
    return validate_external_id(suffix)


def canonical_bidzaar_url(external_id: object) -> str:
    raw_value = str(external_id or "").strip()
    if "://" in raw_value:
        try:
            raw_value = urlparse(raw_value).path.rstrip("/").rsplit("/", 1)[-1]
        except ValueError as exc:
            raise ValueError("Invalid Bidzaar external ID") from exc
    validated = validate_external_id(raw_value)
    if validated is None:
        raise ValueError("Invalid Bidzaar external ID")
    return f"{_CANONICAL_PREFIX}{validated}"
