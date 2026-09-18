"""本地 32B 模型实现（V2.0 启用）：OpenAI 兼容端点（vLLM/Ollama），类签名与 qwen 完全一致。
LLM_PROVIDER=ollama 时启用；端点地址由 OLLAMA_BASE_URL 提供（.env 可扩展）。"""
import json
import logging
from typing import Type

import httpx
from langchain_core.messages import AIMessage
from pydantic import BaseModel, ValidationError

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OllamaLLMProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434/v1", model: str = "qwen2.5:32b") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat(self, messages: list, structured: Type[BaseModel] | None = None):
        payload_msgs = [
            {"role": "user" if m.type == "human" else "assistant", "content": str(m.content)}
            for m in messages
        ]
        body: dict = {"model": self.model, "messages": payload_msgs}
        if structured is not None:
            body["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=body)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        if structured is None:
            return AIMessage(content=content)
        return structured.model_validate_json(content)

    async def stream(self, messages: list):
        payload_msgs = [
            {"role": "user" if m.type == "human" else "assistant", "content": str(m.content)}
            for m in messages
        ]
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json={"model": self.model, "messages": payload_msgs, "stream": True},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        delta = json.loads(data)["choices"][0]["delta"].get("content")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("V2.0 本地 embedding（bge-m3）接入时实现")
