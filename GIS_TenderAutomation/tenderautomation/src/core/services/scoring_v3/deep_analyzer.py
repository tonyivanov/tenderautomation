"""Deep tender analyzer: scrapes description, downloads attached files, runs LLM analysis."""
from __future__ import annotations

import asyncio, logging, os, re, tempfile, time
from dataclasses import dataclass
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup

from .config import DEEPSEEK_API_KEY
from core.models import PlatformCredentials, PlatformDescriptor

logger = logging.getLogger(__name__)

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

ANALYSIS_PROMPT = """Ты — эксперт по анализу B2B тендеров для российской IT-компании Git in Sky.

## Компетенции Git in Sky (кратко):
DevOps, Kubernetes, Docker, Linux администрирование, виртуализация (VMware, Hyper-V, Proxmox),
облачная инфраструктура, аудит IT-инфраструктуры, модернизация инфраструктуры,
миграция серверов и баз данных, серверы и СХД (Ceph, NetApp, SAN),
резервное копирование (Veeam, NetBackup), сетевая инфраструктура,
базы данных (PostgreSQL, MS SQL, Oracle), мониторинг, отказоустойчивость,
техническая поддержка IT-инфраструктуры, IT-аутсорсинг,
аудит информационной безопасности, пентест, средства защиты (WAF, PAM, DLP, NGFW).

## Тендер для анализа:
**Название:** {title}
**Заказчик:** {buyer}
**Бюджет:** {budget}
**Дедлайн:** {deadline}
**Платформа:** {platform}

**Описание с площадки:**
{description}

{files_section}
## Задание:
Проанализируй тендер и дай:
1. **Оценка соответствия**: ⭐ (идеально) / 🟡 (вероятно) / 🟠 (сомнительно) / 🔴 (не подходит)
2. **Какие компетенции GIS закрывает** (перечисли конкретно)
3. **Риски и ограничения** (например: требуется лицензия ФСБ, узкая специализация, жёсткие сроки)
4. **Рекомендация**: брать / уточнить ТЗ / пропустить
5. **Краткое обоснование** (2-4 предложения)

Формат ответа: обычный текст, структурированный по пунктам."""


@dataclass
class DeepAnalysisResult:
    tier: str
    rationale: str
    tool: str = "DeepSeek V4"


# ── Bidzaar auth (cached) ──────────────────────────────────────────────

def _get_bidzaar_token() -> str:
    """Get Bidzaar API token (cached)."""
    from dotenv import load_dotenv; load_dotenv()
    from adapters.bidzaar.auth import BidzaarAuth
    from adapters.bidzaar import BidzaarAdapter

    desc_path = Path(__file__).resolve().parent.parent.parent.parent / "src/adapters/bidzaar/descriptor.yaml"
    desc_data = yaml.safe_load(open(desc_path))
    desc = PlatformDescriptor(**desc_data)
    auth = BidzaarAuth(desc)
    creds = PlatformCredentials(
        platform="bidzaar",
        username=os.getenv("BIDZAAR_USERNAME", ""),
        password=os.getenv("BIDZAAR_PASSWORD", ""),
    )
    session = auth.get_session(creds)
    return session.token


# ── File download & extraction ─────────────────────────────────────────

async def _download_and_extract(client: httpx.AsyncClient, url: str, filename: str) -> str | None:
    """Download a file and extract text content. Returns None if unsupported format."""
    ext = Path(filename).suffix.lower()
    if ext not in (".pdf", ".docx", ".xlsx", ".txt", ".doc", ".rtf"):
        return None

    try:
        r = await client.get(url, timeout=60)
        r.raise_for_status()
    except Exception as e:
        logger.warning("deep_analyzer: download failed %s: %s", filename, e)
        return None

    content = r.content
    if not content:
        return None

    if ext == ".txt":
        return content.decode("utf-8", errors="replace")[:3000]

    if ext == ".pdf":
        try:
            import io, pdfplumber
            text_parts = []
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                for page in pdf.pages[:15]:  # first 15 pages
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
            return "\n".join(text_parts)[:4000] if text_parts else None
        except ImportError:
            return "[PDF: pdfplumber not installed]"
        except Exception as e:
            logger.warning("deep_analyzer: pdf parse failed %s: %s", filename, e)
            return None

    if ext == ".docx":
        try:
            import io, docx
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return text[:4000] if text else None
        except ImportError:
            return "[DOCX: python-docx not installed]"
        except Exception as e:
            logger.warning("deep_analyzer: docx parse failed %s: %s", filename, e)
            return None

    if ext in (".xlsx", ".xls"):
        try:
            import io, openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
            text_parts = []
            for sheet_name in wb.sheetnames[:3]:
                ws = wb[sheet_name]
                text_parts.append(f"[Лист: {sheet_name}]")
                rows = []
                for row in ws.iter_rows(max_row=50, values_only=True):
                    row_text = " | ".join(str(c) if c is not None else "" for c in row)
                    if row_text.strip():
                        rows.append(row_text)
                text_parts.extend(rows[:50])
            return "\n".join(text_parts)[:4000] if text_parts else None
        except ImportError:
            return "[XLSX: openpyxl not installed]"
        except Exception as e:
            logger.warning("deep_analyzer: xlsx parse failed %s: %s", filename, e)
            return None

    return None


# ── Bidzaar file fetching ──────────────────────────────────────────────

async def _fetch_bidzaar_files(tender_url: str) -> list[dict]:
    """Extract UUID from URL, fetch files from Bidzaar main-view API."""
    import re as _re
    m = _re.search(r"/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", tender_url)
    if not m:
        return []

    uuid = m.group(1)
    try:
        token = _get_bidzaar_token()
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"https://bidzaar.com/api/process/light/procedures/read/{uuid}/main-view",
                headers={"Authorization": f"Bearer {token}"},
            )
            if r.status_code != 200:
                return []
            data = r.json()
            return (data.get("generalInformation", {}) or {}).get("files", [])
    except Exception:
        return []


async def _download_bidzaar_files(files: list[dict]) -> str:
    """Download Bidzaar files via Playwright with stored session, extract text."""
    if not files:
        return ""

    import json as _json
    from playwright.async_api import async_playwright

    state_path = Path(__file__).resolve().parent.parent.parent.parent.parent / "data" / "bidzaar_state.json"
    if not state_path.exists():
        return ""

    sections = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            context = await browser.new_context(storage_state=str(state_path))
            page = await context.new_page()
            for f in files[:5]:
                name = f.get("name", "unknown")
                ext = f.get("extension", "")
                full_name = f"{name}.{ext}" if ext else name
                fid = f.get("id", "")
                if not fid:
                    continue
                # Navigate to file detail, capture download
                file_url = f"https://bidzaar.com/app/files/{fid}"
                try:
                    resp = await page.goto(file_url, wait_until="networkidle", timeout=15000)
                    if not resp or resp.status >= 400:
                        continue
                    # Try to get the page content — Bidzaar may serve files inline
                    content = await page.content()
                    text = content[:4000] if len(content) > 100 else None
                    if text and not text.startswith("<"):
                        sections.append(f"### Файл: {full_name}\n{text}")
                except Exception:
                    pass
        finally:
            await browser.close()

    return "\n\n".join(sections) if sections else ""


# ── Page scraping ──────────────────────────────────────────────────────

async def scrape_tender_page(url: str) -> str:
    """Scrape text content from tender page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    async with httpx.AsyncClient(timeout=30, headers=headers, follow_redirects=True, trust_env=False) as client:
        r = await client.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        result = "\n".join(lines)
        if len(result) > 4000:
            result = result[:4000] + "...[truncated]"
        return result


# ── Main analysis ──────────────────────────────────────────────────────

async def analyze_tender(
    title: str,
    url: str,
    buyer: str = "",
    budget: str = "",
    deadline: str = "",
    platform: str = "",
) -> DeepAnalysisResult:
    """Scrape tender page, download files, and run LLM analysis."""
    if not DEEPSEEK_API_KEY:
        raise ValueError("DEEPSEEK_API_KEY not set")

    # Step 1: Scrape description
    logger.info("deep_analyzer: scraping %s", url[:80])
    try:
        description = await scrape_tender_page(url)
    except Exception as e:
        logger.warning("deep_analyzer: scrape failed: %s", e)
        description = f"[Не удалось загрузить описание: {e}]"

    # Step 2: Download and extract files (Bidzaar only for now)
    files_text = ""
    if "bidzaar" in url:
        try:
            files = await _fetch_bidzaar_files(url)
            if files:
                logger.info("deep_analyzer: found %d files", len(files))
                files_text = await _download_bidzaar_files(files)
                if files_text:
                    files_text = f"**Содержимое файлов тендера:**\n{files_text}\n\n"
        except Exception as e:
            logger.warning("deep_analyzer: file download failed: %s", e)

    files_section = files_text if files_text else ""

    # Step 3: Build prompt
    prompt = ANALYSIS_PROMPT.format(
        title=title,
        buyer=buyer or "не указан",
        budget=budget or "не указан",
        deadline=deadline or "не указан",
        platform=platform,
        description=description,
        files_section=files_section,
    )

    # Step 4: Call DeepSeek
    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        r = await client.post(DEEPSEEK_URL, json={
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": "Ты — эксперт по анализу IT-тендеров. Отвечай на русском языке."},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 2048,
            "temperature": 0.3,
        }, headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"})
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]

    latency_ms = int((time.perf_counter() - t0) * 1000)
    logger.info("deep_analyzer: analysis done in %dms", latency_ms)

    # Determine tier
    tier = "🟡"
    if "⭐" in content: tier = "⭐"
    elif "🔴" in content: tier = "🔴"
    elif "🟠" in content: tier = "🟠"

    return DeepAnalysisResult(tier=tier, rationale=content, tool="DeepSeek V4")
