"""Gemini Flash 2.5 client — Google GenAI SDK v2 (free tier: 20 req/day, 250K tokens/min).
Acts as JUDGE for disputed/low-confidence tenders only.
"""
from __future__ import annotations

import json, logging, time
from dataclasses import dataclass

from google import genai
from google.genai import types as genai_types

from . import models
from .prompt_manager import load_judge_prompt, load_user_prompt

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-2.5-flash"


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


def _parse_gemini_response(text: str) -> list[models.LLMClassificationItem]:
    """Gemini returns plain text (no function calling here), extract JSON array."""
    content = text.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"): lines = lines[1:]
        if lines and lines[-1].startswith("```"): lines = lines[:-1]
        content = "\n".join(lines)

    data = None
    errors = []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        errors.append(str(e))

    if data is None:
        import re
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            raw = match.group(0)
            raw = re.sub(r",\s*]", "]", raw)
            raw = re.sub(r",\s*}", "}", raw)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                errors.append(f"regex+fix: {e}")

    if data is None:
        raise ValueError(f"Gemini JSON parse failed. Errors: {'; '.join(errors[-3:])}. Raw: {text[:300]}")

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
    use_judge: bool = True,
    api_key: str = "",
) -> LLMCallResult:
    """Classify a batch using Gemini Flash (judge role only)."""
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    client = genai.Client(api_key=api_key)
    system_prompt = load_judge_prompt()
    user_message = _build_user_message(tender_titles)

    t0 = time.perf_counter()
    response = await client.aio.models.generate_content(
        model=GEMINI_MODEL,
        contents=f"{system_prompt}\n\n{user_message}",
        config=genai_types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192,
        ),
    )

    text = response.text if response.text else ""
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage else 0
    output_tokens = usage.candidates_token_count if usage else 0

    items = _parse_gemini_response(text)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    logger.info("Gemini judge: items=%d tokens=%d/%d latency=%dms",
        len(items), input_tokens, output_tokens, latency_ms)
    return LLMCallResult(items=items, model_used=GEMINI_MODEL,
        input_tokens=input_tokens, output_tokens=output_tokens,
        estimated_cost=0.0, latency_ms=latency_ms, attempts=1)