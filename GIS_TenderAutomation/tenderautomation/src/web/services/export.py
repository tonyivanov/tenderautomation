from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from core.logging import get_logger
from core.models import TenderModel
from core.repositories import TenderRepository

log = get_logger(__name__)

_AGENTS_MD_PATH = Path("AGENTS.md")
_CONFIG_PATH = Path("filters/config.yaml")


class ExportService:
    def __init__(self, tender_repo: TenderRepository) -> None:
        self._tender_repo = tender_repo

    def build_zip(self, tender_ids: list[str] | None = None) -> io.BytesIO:
        tenders = self._get_tenders(tender_ids)
        jsonl = self._build_jsonl(tenders)
        agents_md = self._build_agents_md()
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"tenders_{date_str}.jsonl", jsonl)
            zf.writestr("AGENTS.md", agents_md)
        buf.seek(0)

        log.info("export_zip_built", extra={"context": {
            "tenders": len(tenders), "date": date_str
        }})
        return buf

    def _get_tenders(self, tender_ids: list[str] | None) -> list[TenderModel]:
        if tender_ids:
            tenders = [t for tid in tender_ids if (t := self._tender_repo.get_by_id(tid))]
        else:
            tenders = self._tender_repo.get_qualified(limit=1000)
        return tenders

    @staticmethod
    def _build_jsonl(tenders: list[TenderModel]) -> str:
        lines = [json.dumps(t.to_jsonl_dict(), ensure_ascii=False) for t in tenders]
        return "\n".join(lines) + ("\n" if lines else "")

    @staticmethod
    def _build_agents_md() -> str:
        base = _AGENTS_MD_PATH.read_text(encoding="utf-8") if _AGENTS_MD_PATH.exists() else ""

        profile_block = ""
        if _CONFIG_PATH.exists():
            config = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
            profile = config.get("semantic_profile", {})
            if profile:
                lines = ["## Company Profile (for AI Agent)", ""]
                lines.append(f"**Company**: {profile.get('company', 'Git in Sky')}")
                lines.append("")
                lines.append("**Focus areas** (relevant tender categories):")
                for area in profile.get("focus_areas", []):
                    lines.append(f"- {area}")
                lines.append("")
                lines.append("**Exclude areas** (not relevant):")
                for area in profile.get("exclude_areas", []):
                    lines.append(f"- {area}")
                profile_block = "\n".join(lines)

        return base.replace("{{SEMANTIC_PROFILE}}", profile_block)
