"""通义千问实现（LangChain 1.0）：init_chat_model + OpenAI 兼容模式。

- 公网 DashScope：QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1（默认）
- 专属推理端点：QWEN_BASE_URL=https://xxxx.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
  专属端点的 API-KEY（sk-ws 开头）必须与对应端点搭配，否则 401。
- 结构化输出在 json_schema / function_calling 间自动降级并记住可用方式（文档 14.1）。
"""
import asyncio
import logging
from typing import Type

from langchain_core.messages import AIMessage
from pydantic import BaseModel

from app.core.config import get_settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class LLMAuthError(RuntimeError):
    """API 鉴权失败（401/403）：不可重试，必须向上透传给用户。"""


def _wrap_auth_error(exc: Exception) -> Exception:
    text = str(exc)
    if "401" in text or "403" in text or "invalid_api_key" in text:
        return LLMAuthError(
            "qwen API 鉴权失败（401）：API-KEY 与端点不匹配。"
            "专属端点(*.maas.aliyuncs.com)的 key 必须搭配对应的 QWEN_BASE_URL；"
            "公网 DashScope key 则使用默认端点。请核对 backend/.env 后重启服务。"
        )
    return exc


class QwenLLMProvider(LLMProvider):
    MAX_RETRY = 2  # 首次失败后再重试 2 次（文档 14.1）
    _ok_method: str | None = None  # 记住当前模型可用的结构化输出方式

    def _chat_model(self):
        from langchain.chat_models import init_chat_model

        s = get_settings()
        return init_chat_model(
            model=s.qwen_model,
            model_provider="openai",
            api_key=s.qwen_api_key.strip(),
            base_url=s.qwen_base_url,
            timeout=s.qwen_timeout_sec,   # 防止慢端点把事件循环"卡死"
            max_retries=0,                # 重试由本类统一管理（含鉴权快速失败）
        )

    async def chat(self, messages: list, structured: Type[BaseModel] | None = None):
        if structured is None:
            return await self._plain_with_retry(messages)

        methods = [self._ok_method] if self._ok_method else ["json_schema", "function_calling"]
        last_err: Exception | None = None
        for method in methods:
            for attempt in range(1 + self.MAX_RETRY):
                try:
                    runner = self._chat_model().with_structured_output(structured, method=method)
                    result = await runner.ainvoke(messages)
                    if not isinstance(result, structured):
                        result = structured.model_validate(result)
                    self._ok_method = method
                    return result
                except Exception as exc:  # noqa: BLE001
                    # 鉴权失败重试无意义：立即快速失败并给出可操作提示
                    if "401" in str(exc) or "403" in str(exc) or "invalid_api_key" in str(exc):
                        raise _wrap_auth_error(exc) from exc
                    last_err = exc
                    logger.warning("qwen 结构化输出[%s] 第 %d 次失败: %s", method, attempt + 1, exc)
                    if attempt < self.MAX_RETRY:
                        await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"qwen 结构化输出连续失败（已尝试 {methods}）: {last_err}")

    async def _plain_with_retry(self, messages: list):
        last_err: Exception | None = None
        for attempt in range(1 + self.MAX_RETRY):
            try:
                resp = await self._chat_model().ainvoke(messages)
                return resp if isinstance(resp, AIMessage) else AIMessage(content=str(resp))
            except Exception as exc:  # noqa: BLE001
                if "401" in str(exc) or "403" in str(exc) or "invalid_api_key" in str(exc):
                    raise _wrap_auth_error(exc) from exc
                last_err = exc
                logger.warning("qwen 对话第 %d 次失败: %s", attempt + 1, exc)
                await asyncio.sleep(0.5 * (attempt + 1))
        raise RuntimeError(f"qwen 调用连续失败: {last_err}")

    async def stream(self, messages: list):
        model = self._chat_model()
        async for chunk in model.astream(messages):
            if chunk.content:
                yield chunk.content if isinstance(chunk.content, str) else str(chunk.content)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Embedding 走 OpenAI 兼容 /embeddings（默认公网 DashScope，text-embedding-v3, 1024 维）。"""
        import httpx

        s = get_settings()
        url = s.embedding_base_url.rstrip("/") + "/embeddings"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {s.qwen_api_key.strip()}"},
                json={"model": s.embedding_model, "input": texts, "dimensions": 1024},
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            return [item["embedding"] for item in sorted(data, key=lambda x: x["index"])]
