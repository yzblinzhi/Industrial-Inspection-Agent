"""Provider 抽象基类：Mock 与真实实现共同契约，节点只依赖抽象（文档 6.1）。"""
from abc import ABC, abstractmethod
from typing import Type

from pydantic import BaseModel, Field


class CVProvider(ABC):
    """视觉检测：输入 MinIO object key，输出统一缺陷检测契约（schemas.cv.CVResult）。"""

    @abstractmethod
    async def detect(self, image_key: str, workpiece_no: str) -> dict: ...


class RAGDoc(BaseModel):
    doc_id: str
    title: str
    text: str
    score: float = 0.0
    params: dict = Field(default_factory=dict, description="工艺参数取值范围，如 {\"喷涂压力_MPa\": [0.30, 0.40]}")


class RAGProvider(ABC):
    """工艺知识检索：返回带 doc_id 与参数范围的文档列表（供自检溯源）。"""

    @abstractmethod
    async def retrieve(self, query: str, top_k: int = 3) -> list[dict]: ...


class LLMProvider(ABC):
    """大模型：chat（结构化可选）/ stream（逐 token）/ embed。"""

    @abstractmethod
    async def chat(self, messages: list, structured: Type[BaseModel] | None = None): ...

    @abstractmethod
    async def stream(self, messages: list): ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
