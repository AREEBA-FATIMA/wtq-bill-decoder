"""Configuration from environment variables (.env supported)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ALLOWED_MODELS = {
    "anthropic": {"claude-haiku-4-5"},
    "google": {"gemini-3.5-flash-lite", "gemini-3.1-flash-lite"},
    "openai": {"gpt-4.1-mini", "gpt-5-mini"},
}

DEFAULT_MODEL = {
    "anthropic": "claude-haiku-4-5",
    "google": "gemini-3.1-flash-lite",
    "openai": "gpt-4.1-mini",
}


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    provider: str
    model_name: str
    api_key: str
    cache_dir: Path
    min_interval_sec: float
    max_image_side: int
    fewshot_image: Path | None
    fallback_model: str | None
    max_attempts: int


def load_settings(require_key: bool = True) -> Settings:
    load_dotenv()
    provider = os.getenv("MODEL_PROVIDER", "google").strip().lower()
    if provider not in ALLOWED_MODELS:
        raise ConfigError(f"MODEL_PROVIDER must be one of {sorted(ALLOWED_MODELS)}, got {provider!r}")

    model = os.getenv("MODEL_NAME", DEFAULT_MODEL[provider]).strip()
    if model not in ALLOWED_MODELS[provider]:
        raise ConfigError(
            f"MODEL_NAME {model!r} is not an allowed {provider} model: {sorted(ALLOWED_MODELS[provider])}"
        )

    api_key = os.getenv("API_KEY", "").strip()
    if require_key and (not api_key or api_key == "your-api-key-here"):
        raise ConfigError("API_KEY is not set. Copy .env.example to .env and add your key.")

    fallback = os.getenv("FALLBACK_MODEL", "").strip()
    if not fallback and provider == "google":
        fallback = next(m for m in sorted(ALLOWED_MODELS["google"]) if m != model)
    if fallback and fallback not in ALLOWED_MODELS[provider]:
        raise ConfigError(f"FALLBACK_MODEL {fallback!r} is not an allowed {provider} model")

    default_interval = "4.5" if provider == "google" else "0"
    fewshot = os.getenv("FEWSHOT_IMAGE", "").strip()
    return Settings(
        provider=provider,
        model_name=model,
        api_key=api_key,
        cache_dir=Path(os.getenv("CACHE_DIR", ".cache")),
        min_interval_sec=float(os.getenv("MIN_INTERVAL_SEC", default_interval)),
        max_image_side=int(os.getenv("MAX_IMAGE_SIDE", "2000")),
        fewshot_image=Path(fewshot) if fewshot else None,
        fallback_model=fallback if fallback and fallback != model else None,
        max_attempts=int(os.getenv("MAX_ATTEMPTS", "8")),
    )
