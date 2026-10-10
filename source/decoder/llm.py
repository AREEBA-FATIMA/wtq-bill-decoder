"""Thin multimodal LLM client: provider switch, JSON parsing, retries, pacing, disk cache."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import re
import threading
import time
from pathlib import Path

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import ConfigError, Settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a meticulous assistant for Pakistani electricity bills (K-Electric, LESCO, IESCO). "
    "You read bill images exactly, never invent values, never reveal personal identifiers, "
    "and always reply with a single valid JSON object and nothing else."
)


class LLMError(RuntimeError):
    pass


def parse_json_object(text: str) -> dict:
    """Extract the first top-level JSON object from model text (tolerates code fences)."""
    if not text:
        raise LLMError("empty model response")
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise LLMError(f"no JSON object in response: {text[:200]!r}") from None
        try:
            data = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"invalid JSON from model: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMError("model returned JSON that is not an object")
    return data


class LLMClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self._lock = threading.Lock()
        self._last_call = 0.0
        self.calls = 0
        self.cache_hits = 0
        settings.cache_dir.mkdir(parents=True, exist_ok=True)

        if settings.provider == "google":
            from google import genai

            self._client = genai.Client(api_key=settings.api_key)
        elif settings.provider == "anthropic":
            import anthropic

            self._client = anthropic.Anthropic(api_key=settings.api_key, max_retries=2)
        else:
            raise ConfigError(f"Provider {settings.provider!r} is not implemented; use google or anthropic.")

    # ---------- public ----------
    def json_call(self, prompt: str, images: list[bytes] | None = None, tag: str = "call") -> dict:
        """Send prompt + images, return parsed JSON object. Cached by content hash."""
        images = images or []
        key = self._cache_key(prompt, images)
        cache_file = self.s.cache_dir / f"{tag}_{key}.json"
        if cache_file.exists():
            self.cache_hits += 1
            return json.loads(cache_file.read_text(encoding="utf-8"))

        data = self._call_and_parse(prompt, images)
        cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        return data

    def ping(self) -> str:
        data = self._call_and_parse('Reply with exactly this JSON: {"ok": true}', [])
        return json.dumps(data)

    # ---------- internals ----------
    def _cache_key(self, prompt: str, images: list[bytes]) -> str:
        h = hashlib.sha256()
        h.update(f"{self.s.provider}|{self.s.model_name}|".encode())
        h.update(prompt.encode("utf-8"))
        for img in images:
            h.update(hashlib.sha256(img).digest())
        return h.hexdigest()[:24]

    def _pace(self) -> None:
        with self._lock:
            wait = self.s.min_interval_sec - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    @retry(
        reraise=True,
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda rs: log.warning("LLM call failed (%s); retrying…", rs.outcome.exception()),
    )
    def _call_and_parse(self, prompt: str, images: list[bytes]) -> dict:
        self._pace()
        self.calls += 1
        if self.s.provider == "google":
            text = self._call_google(prompt, images)
        else:
            text = self._call_anthropic(prompt, images)
        return parse_json_object(text)

    def _call_google(self, prompt: str, images: list[bytes]) -> str:
        from google.genai import types

        parts: list = [types.Part.from_bytes(data=img, mime_type="image/png") for img in images]
        parts.append(prompt)
        resp = self._client.models.generate_content(
            model=self.s.model_name,
            contents=parts,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0,
                response_mime_type="application/json",
                max_output_tokens=8192,
            ),
        )
        return resp.text or ""

    def _call_anthropic(self, prompt: str, images: list[bytes]) -> str:
        content: list[dict] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(img).decode()},
            }
            for img in images
        ]
        content.append({"type": "text", "text": prompt})
        resp = self._client.messages.create(
            model=self.s.model_name,
            max_tokens=8192,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")


def cache_path(settings: Settings) -> Path:
    return settings.cache_dir
