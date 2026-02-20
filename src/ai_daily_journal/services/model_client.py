from __future__ import annotations

import json
from typing import Any

import httpx


class ModelClientError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def chat(self, *, model: str, system_prompt: str, user_prompt: str, temperature: float) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
        }
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise ModelClientError(f"Model request failed: {response.status_code} {response.text}")
        data = response.json()
        try:
            return str(data["choices"][0]["message"]["content"])
        except Exception as exc:  # noqa: BLE001
            raise ModelClientError(f"Invalid model response shape: {json.dumps(data)[:500]}") from exc

    def embedding(self, *, model: str, text: str) -> list[float]:
        payload = {"model": model, "input": text}
        response = httpx.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise ModelClientError(f"Embedding request failed: {response.status_code} {response.text}")
        data = response.json()
        try:
            return [float(v) for v in data["data"][0]["embedding"]]
        except Exception as exc:  # noqa: BLE001
            raise ModelClientError(f"Invalid embeddings response shape: {json.dumps(data)[:500]}") from exc
