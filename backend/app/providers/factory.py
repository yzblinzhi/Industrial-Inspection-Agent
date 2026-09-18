"""Provider 工厂：按 .env 配置实例化，节点代码零修改切换 Mock ↔ 真实组件（文档 6.4）。"""
from functools import lru_cache

from app.core.config import get_settings
from app.providers.base import CVProvider, LLMProvider, RAGProvider


@lru_cache
def get_cv_provider() -> CVProvider:
    name = get_settings().cv_provider
    if name == "mock":
        from app.providers.cv_mock import MockCVProvider

        return MockCVProvider()
    if name == "yolo_http":
        from app.providers.cv_yolo_http import YoloHttpProvider

        return YoloHttpProvider()
    raise ValueError(f"未知 CV_PROVIDER: {name}")


@lru_cache
def get_rag_provider() -> RAGProvider:
    name = get_settings().rag_provider
    if name == "mock":
        from app.providers.rag_mock import MockRAGProvider

        return MockRAGProvider()
    if name == "redis_vector":
        from app.providers.rag_redis import RedisVectorRAGProvider

        return RedisVectorRAGProvider()
    raise ValueError(f"未知 RAG_PROVIDER: {name}")


@lru_cache
def get_llm_provider() -> LLMProvider:
    name = get_settings().llm_provider
    if name == "mock":
        from app.providers.llm_mock import MockLLMProvider

        return MockLLMProvider()
    if name == "qwen":
        from app.providers.llm_qwen import QwenLLMProvider

        return QwenLLMProvider()
    if name == "ollama":
        from app.providers.llm_ollama import OllamaLLMProvider

        return OllamaLLMProvider()
    raise ValueError(f"未知 LLM_PROVIDER: {name}")
