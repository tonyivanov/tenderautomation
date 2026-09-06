"""Scoring v3 — configuration from environment."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()  # Load .env into os.environ (pydantic-settings does NOT do this)

OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_MODEL_PRIMARY: str = os.getenv("OPENROUTER_MODEL_PRIMARY", "openai/gpt-4o-mini")
OPENROUTER_MODEL_JUDGE: str = os.getenv("OPENROUTER_MODEL_JUDGE", "anthropic/claude-3.5-haiku")
_RAW_FALLBACKS: str = os.getenv("OPENROUTER_MODEL_FALLBACKS", "")
OPENROUTER_MODEL_FALLBACKS: list[str] = [m.strip() for m in _RAW_FALLBACKS.split(",") if m.strip()]

OPENROUTER_TIMEOUT_SECONDS: int = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "90"))
OPENROUTER_MAX_CONCURRENCY: int = int(os.getenv("OPENROUTER_MAX_CONCURRENCY", "3"))
OPENROUTER_DAILY_BUDGET: float = float(os.getenv("OPENROUTER_DAILY_BUDGET", "5.0"))
OPENROUTER_HTTP_REFERER: str = os.getenv("OPENROUTER_HTTP_REFERER", "")
OPENROUTER_APP_TITLE: str = os.getenv("OPENROUTER_APP_TITLE", "GIS_TenderAutomation")

LLM_BATCH_SIZE: int = int(os.getenv("LLM_BATCH_SIZE", "20"))
PROMPT_VERSION: str = os.getenv("PROMPT_VERSION", "gis-tender-v3.0")

# ── Queue thresholds ─────────────────────────────────────────────────────
P1_MIN_FIT_SCORE: int = 75
P1_MIN_CONFIDENCE: float = 0.82
REJECT_MIN_CONFIDENCE: float = 0.85
JUDGE_MIN_CONFIDENCE: float = 0.80
P3_SAMPLE_RATE: float = 0.05

# ── Free tier LLM API keys ────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
