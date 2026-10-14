"""Cliente HTTP para KoboldCpp (API OpenAI-compatible)."""

import json
import httpx
from typing import AsyncIterator


class KoboldClient:
    def __init__(self, base_url: str, model: str, api_key: str = "local"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            r.raise_for_status()
            return [m["id"] for m in r.json().get("data", [])]

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> dict:
        """Petición NO streaming. Devuelve el mensaje completo del asistente."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient(timeout=600) as client:
            r = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]

    async def stream_chat(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 2048
    ) -> AsyncIterator[str]:
        """Streaming SSE (sin tools)."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=600) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
