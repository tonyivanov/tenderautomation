"""Direct DeepSeek API client (V4 Flash) — OpenAI-compatible format."""
from __future__ import annotations

import asyncio, json, logging, time
from dataclasses import dataclass

import httpx

from . import models
from .prompt_manager import load_system_prompt, load_judge_prompt, load_user_prompt

logger = logging.getLogger(__name__)

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"


@dataclass
class LLMCallResult:
    items: list[models.LLMClassificationItem]
    model_used: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    latency_ms: int
    attempts: int


def _build_user_message(tender_titles: list[str]) -> str:
    template = load_user_prompt()
    items = [json.dumps({"id": f"t{i+1}", "title": t}, ensure_ascii=False) for i, t in enumerate(tender_titles)]
    return template.replace("{{TENDERS_JSON}}", "[\n  " + ",\n  ".join(items) + "\n]")


def _parse_llm_response(raw_content: str) -> list[models.LLMClassificationItem]:
    content = raw_content.strip()
    # Strip ```json fences
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"): lines = lines[1:]
        if lines and lines[-1].startswith("```"): lines = lines[:-1]
        content = "\n".join(lines)

    data = None
    errors = []

    # Attempt 1: direct parse
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        errors.append(str(e))

    # Attempt 2: regex find JSON array, fix trailing commas
    if data is None:
        import re
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            raw = match.group(0)
            # Fix common JSON errors: trailing comma before ], missing quotes in strings
            raw = re.sub(r",\s*]", "]", raw)  # trailing comma before ]
            raw = re.sub(r",\s*}", "}", raw)  # trailing comma before }
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                errors.append(f"regex+fix: {e}")

    # Attempt 3: line-by-line truncation (remove last incomplete object)
    if data is None:
        import re
        for trim in range(5, 50, 5):
            match = re.search(r"\[.*\]", content[:len(content)-trim], re.DOTALL)
            if not match:
                continue
            raw = re.sub(r",\s*]", "]", match.group(0))
            raw = re.sub(r",\s*}", "}", raw)
            try:
                data = json.loads(raw)
                if data and isinstance(data, list) and len(data) > 0:
                    break
            except json.JSONDecodeError:
                continue

    if data is None:
        raise ValueError(f"Cannot parse JSON after 3 attempts. Errors: {'; '.join(errors[-3:])}. Raw: {raw_content[:300]}")
    items = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        raw_v = str(entry.get("verdict", "review")).strip().lower()
        if raw_v not in ("core", "review", "reject"):
            raw_v = "review"
        raw_d = str(entry.get("primary_domain", "unknown")).strip()
        from .openrouter_client import _map_domain
        primary_domain = _map_domain(raw_d)
        items.append(models.LLMClassificationItem(
            id=str(entry.get("id", "")),
            verdict=raw_v,
            fit_score=int(entry.get("fit_score", 50)),
            confidence=float(entry.get("confidence", 0.5)),
            procurement_type=str(entry.get("procurement_type", "unknown")),
            primary_domain=primary_domain,
            secondary_domains=entry.get("secondary_domains", []),
            needs_documents=bool(entry.get("needs_documents", False)),
            positive_evidence=entry.get("positive_evidence", []),
            negative_evidence=entry.get("negative_evidence", []),
            risk_flags=entry.get("risk_flags", []),
            reason=str(entry.get("reason", "")),
        ))
    return items


async def classify_batch(
    tender_titles: list[str],
    *,
    use_judge: bool = False,
    api_key: str = "",
) -> LLMCallResult:
    """Classify a batch using DeepSeek API directly."""
    system_prompt = load_judge_prompt() if use_judge else load_system_prompt()
    user_message = _build_user_message(tender_titles)

    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        r = await client.post(DEEPSEEK_URL, json={
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 8192,
            "temperature": 0.1,
        }, headers={"Authorization": f"Bearer {api_key}"})
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        items = _parse_llm_response(content)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        logger.info("DeepSeek %s: items=%d tokens=%d/%d latency=%dms",
            "judge" if use_judge else "primary", len(items), input_tokens, output_tokens, latency_ms)
        return LLMCallResult(items=items, model_used=DEEPSEEK_MODEL,
            input_tokens=input_tokens, output_tokens=output_tokens,
            estimated_cost=0.0, latency_ms=latency_ms, attempts=1)