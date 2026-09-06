"""OpenRouter Chat Completions API client for LLM tender classification.

Supports:
- Primary model batch classification
- Judge model for independent re-classification
- Retry with exponential backoff + jitter (2s → 5s → 15s)
- Fallback model chain
- JSON Schema response validation
- Token usage and cost tracking
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from typing import Any, cast

import httpx

from . import config, models
from .prompt_manager import load_system_prompt, load_judge_prompt, load_user_prompt

logger = logging.getLogger(__name__)

RETRY_SCHEDULE = [2.0, 5.0, 15.0]  # seconds
JITTER_MAX = 0.4  # ±0.4s jitter
_JITTER_RNG = random.SystemRandom()


@dataclass
class LLMCallResult:
    items: list[models.LLMClassificationItem]
    model_used: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    latency_ms: int
    attempts: int


def _build_client(timeout: int | None = None) -> httpx.AsyncClient:
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    if config.OPENROUTER_HTTP_REFERER:
        headers["HTTP-Referer"] = config.OPENROUTER_HTTP_REFERER
    if config.OPENROUTER_APP_TITLE:
        headers["X-Title"] = config.OPENROUTER_APP_TITLE
    return httpx.AsyncClient(
        base_url=config.OPENROUTER_BASE_URL,
        headers=headers,
        timeout=httpx.Timeout(timeout or config.OPENROUTER_TIMEOUT_SECONDS),
        trust_env=False,  # Bypass system proxy (SOCKS4 not supported by httpx)
    )


def _build_user_message(tender_titles: list[str]) -> str:
    """Build user message from template and inject tender JSON array."""
    template = load_user_prompt()
    # Build compact JSON array: [{"id": "t1","title":"..."}, ...]
    items = []
    for i, title in enumerate(tender_titles):
        items.append(json.dumps({"id": f"t{i + 1}", "title": title}, ensure_ascii=False))
    tenders_json = "[\n  " + ",\n  ".join(items) + "\n]"
    return template.replace("{{TENDERS_JSON}}", tenders_json)


# ── Domain mapping: Russian → English enum ──────────────────────────────
_DOMAIN_MAP = {
    "резервное копирование": "backup",
    "IT-инфраструктура": "managed_infrastructure",
    "миграция": "infrastructure_migration",
    "техническая поддержка": "managed_infrastructure",
    "IT-аутсорсинг": "managed_infrastructure",
    "модернизация": "infrastructure_modernization",
    "сетевая инфраструктура": "network_infrastructure",
    "информационная безопасность": "information_security",
    "тестирование на проникновение": "information_security",
    "аудит IT-инфраструктуры": "infrastructure_audit",
    "облачная инфраструктура": "cloud_iaas",
    "виртуализация": "virtualization",
    "devops": "devops",
    "контейнеры": "containers",
    "linux_администрирование": "linux_administration",
    "серверы": "servers",
    "системы хранения": "storage",
    "базы данных": "databases",
    "мониторинг": "monitoring",
    "ЦОД": "data_center",
    "телефония": "telephony",
    "прикладное ПО": "application_software",
    "1С": "application_software",
    "офисная IT-инфраструктура": "office_it",
    "веб и маркетинг": "web_and_marketing",
    "инженерная инфраструктура": "facilities",
    "не IT": "non_it",
    "поставка": "supply",
}

ALLOWED_DOMAINS = frozenset({
    "devops", "linux_administration", "containers", "virtualization",
    "cloud_iaas", "infrastructure_audit", "infrastructure_modernization",
    "infrastructure_migration", "managed_infrastructure", "network_infrastructure",
    "servers", "storage", "backup", "databases", "monitoring",
    "information_security", "data_center", "telephony", "office_it",
    "application_software", "web_and_marketing", "facilities", "supply",
    "non_it", "unknown",
})


def _map_domain(raw: str) -> str:
    """Map Russian or freeform domain names to English enum values."""
    if not raw:
        return "unknown"
    low = raw.lower().strip()
    # Direct match in allowed set
    if low in ALLOWED_DOMAINS:
        return low
    # Try Russian mapping
    if low in _DOMAIN_MAP:
        return _DOMAIN_MAP[low]
    # Substring match
    for ru, en in _DOMAIN_MAP.items():
        if ru in low:
            return en
    return "unknown"


def _parse_llm_response(raw_content: str, tender_ids: list[str]) -> list[models.LLMClassificationItem]:
    """Parse JSON array from LLM response into LLMClassificationItem list."""
    # Try to find JSON array in the response
    content = raw_content.strip()
    # Remove markdown code fences if present
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines)

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Try to find JSON array in the text
        import re
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            raise ValueError(f"Cannot find JSON array in LLM response: {raw_content[:500]}")
        data = json.loads(match.group(0))

    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}")

    items: list[models.LLMClassificationItem] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id", "")
        raw_verdict = str(entry.get("verdict", "review")).strip().lower()
        # Sanitize: LLM sometimes confuses procurement_type with verdict
        if raw_verdict not in ("core", "review", "reject"):
            raw_verdict = "review"
        # Map Russian domain names → English enum
        raw_domain = str(entry.get("primary_domain", "unknown")).strip()
        primary_domain = _map_domain(raw_domain)
        items.append(models.LLMClassificationItem(
            id=item_id,
            verdict=raw_verdict,
            fit_score=int(entry.get("fit_score", 50)),
            confidence=float(entry.get("confidence", 0.5)),
            procurement_type=entry.get("procurement_type", "unknown"),
            primary_domain=primary_domain,
            secondary_domains=entry.get("secondary_domains", []),
            needs_documents=bool(entry.get("needs_documents", False)),
            positive_evidence=entry.get("positive_evidence", []),
            negative_evidence=entry.get("negative_evidence", []),
            risk_flags=entry.get("risk_flags", []),
            reason=str(entry.get("reason", "")),
        ))
    return items


async def _call_openrouter(
    client: httpx.AsyncClient,
    model: str,
    system_prompt: str,
    user_message: str,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """Make a single API call to OpenRouter. Returns parsed response JSON."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }

    response = await client.post("/chat/completions", json=payload)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("OpenRouter returned a non-object response")
    return cast(dict[str, Any], data)


async def classify_batch(
    tender_titles: list[str],
    *,
    use_judge: bool = False,
) -> LLMCallResult:
    """Classify a batch of tender titles using primary or judge model."""
    if not config.OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set")

    system_prompt = load_judge_prompt() if use_judge else load_system_prompt()
    user_message = _build_user_message(tender_titles)

    primary_model = config.OPENROUTER_MODEL_JUDGE if use_judge else config.OPENROUTER_MODEL_PRIMARY
    fallback_models = config.OPENROUTER_MODEL_FALLBACKS.copy()

    models_to_try = [primary_model] + fallback_models
    last_error: Exception | None = None
    total_attempts = 0
    t0 = time.perf_counter()

    async with _build_client() as client:
        for model in models_to_try:
            for attempt_idx, delay in enumerate(RETRY_SCHEDULE + [0]):
                if attempt_idx > 0:
                    jitter = _JITTER_RNG.uniform(-JITTER_MAX, JITTER_MAX)
                    await asyncio.sleep(max(0, delay + jitter))
                total_attempts += 1
                try:
                    raw = await _call_openrouter(client, model, system_prompt, user_message)
                    choice = raw["choices"][0]
                    content = choice["message"].get("content")
                    if content is None:
                        raise ValueError("LLM returned None content")
                    usage = raw.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)
                    pricing = raw.get("pricing", {})
                    if pricing:
                        estimated_cost = float(pricing.get("total_cost", 0))
                    else:
                        estimated_cost = (input_tokens * 0.15 + output_tokens * 0.60) / 1_000_000
                    items = _parse_llm_response(content, tender_ids=[f"t{j+1}" for j in range(len(tender_titles))])
                    latency_ms = int((time.perf_counter() - t0) * 1000)
                    logger.info("OpenRouter %s: model=%s items=%d tokens=%d/%d cost=$%.4f latency=%dms attempts=%d",
                        "judge" if use_judge else "primary", model, len(items),
                        input_tokens, output_tokens, estimated_cost, latency_ms, total_attempts)
                    return LLMCallResult(items=items, model_used=model,
                        input_tokens=input_tokens, output_tokens=output_tokens,
                        estimated_cost=estimated_cost, latency_ms=latency_ms, attempts=total_attempts)
                except (httpx.HTTPError, httpx.TimeoutException, json.JSONDecodeError, ValueError) as e:
                    last_error = e
                    error_response = getattr(e, "response", None)
                    status_code = (
                        error_response.status_code
                        if isinstance(error_response, httpx.Response)
                        else None
                    )
                    if status_code == 429 or (status_code and status_code >= 500):
                        logger.warning("OpenRouter %s attempt %d/%d: %s (status=%s)",
                            model, attempt_idx + 1, len(RETRY_SCHEDULE) + 1, e, status_code)
                    elif status_code and 400 <= status_code < 500 and status_code != 429:
                        logger.warning("OpenRouter %s client error (status=%s), skipping model: %s",
                            model, status_code, e)
                        break
                    else:
                        logger.warning("OpenRouter %s attempt %d/%d: %s",
                            model, attempt_idx + 1, len(RETRY_SCHEDULE) + 1, e)

    raise RuntimeError(
        f"OpenRouter classification failed after {total_attempts} attempts across "
        f"{len(models_to_try)} models. Last error: {last_error}"
    )


async def classify_single(
    title: str,
    *,
    use_judge: bool = False,
) -> LLMCallResult:
    """Classify a single tender title."""
    return await classify_batch([title], use_judge=use_judge)
