"""Optional structured-output providers; no provider is contacted by default."""
from __future__ import annotations

import json
from typing import Any

import httpx


class ProviderUnavailable(RuntimeError):
    pass


class LLMProvider:
    name = "unknown"

    def extract(self, text: str, schema: Any) -> Any:
        raise NotImplementedError


class DisabledProvider(LLMProvider):
    name = "disabled"

    def extract(self, text: str, schema: Any) -> Any:
        raise ProviderUnavailable("LLM provider is disabled; use deterministic extraction or configure a provider")


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout_seconds: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def extract(self, text: str, schema: Any) -> Any:
        prompt = (
            "Extract only facts explicitly present in the input. Return valid JSON matching this schema. "
            "Use empty values for missing facts; do not infer.\n"
            f"Schema: {json.dumps(schema.model_json_schema())}\nInput:\n{text}"
        )
        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False, "format": schema.model_json_schema()},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json().get("response")
            return schema.model_validate_json(payload)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise ProviderUnavailable(f"Ollama structured extraction failed: {exc}") from exc


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout_seconds: int):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def extract(self, text: str, schema: Any) -> Any:
        if not self.api_key:
            raise ProviderUnavailable("Gemini provider requires LLM_API_KEY")
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        prompt = (
            "Extract only facts explicitly present. Do not infer missing facts. Return JSON matching this schema:\n"
            f"{json.dumps(schema.model_json_schema())}\nInput:\n{text}"
        )
        try:
            response = httpx.post(
                endpoint,
                params={"key": self.api_key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"},
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            text_result = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return schema.model_validate_json(text_result)
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError) as exc:
            raise ProviderUnavailable(f"Gemini structured extraction failed ({type(exc).__name__})") from exc


def get_provider(settings: Any) -> LLMProvider:
    provider = (settings.llm_provider or "disabled").strip().lower()
    if provider == "ollama":
        return OllamaProvider(settings.llm_base_url, settings.llm_model, settings.llm_timeout_seconds)
    if provider == "gemini":
        return GeminiProvider(settings.llm_api_key, settings.llm_model, settings.llm_timeout_seconds)
    if provider == "disabled":
        return DisabledProvider()
    raise ProviderUnavailable(f"Unsupported LLM_PROVIDER: {provider}")
