"""RAG 真向量实现（第三阶段启用）：DashScope embedding(1024) + Redis-Stack DB0 RediSearch HNSW。
索引与文档写入见 scripts/seed_mock_data.py 的 build_vector_index。"""
import json

import redis
import redis.commands.search.field as sfield
import redis.commands.search.query as squery

from app.core.config import get_settings
from app.providers.base import RAGProvider

INDEX_NAME = "idx:knowledge"
PREFIX = "qc:vec:"
DIM = 1024  # text-embedding-v3 与 bge-m3 同维度，迁移本地模型免重建


class RedisVectorRAGProvider(RAGProvider):
    def __init__(self) -> None:
        s = get_settings()
        self.client = redis.from_url(s.redis_vector_dsn, decode_responses=True)

    async def _get_embedding(self, text: str) -> list[float]:
        from app.providers.factory import get_llm_provider

        return (await get_llm_provider().embed([text]))[0]

    async def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        try:
            vec = await self._get_embedding(query)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"embedding 调用失败: {exc}") from exc

        q = (
            squery.Query(f"(*)=>[KNN {top_k} @vec $vec AS dist]")
            .sort_by("dist")
            .return_fields("doc_id", "title", "text", "params", "dist")
            .dialect(2)
        )
        res = self.client.ft(INDEX_NAME).search(q, {"vec": _to_bytes(vec)})
        docs = []
        for row in res.docs:
            docs.append(
                {
                    "doc_id": getattr(row, "doc_id", ""),
                    "title": getattr(row, "title", ""),
                    "text": getattr(row, "text", ""),
                    "score": round(1.0 - float(getattr(row, "dist", 1.0)), 3),
                    "params": json.loads(getattr(row, "params", "{}") or "{}"),
                }
            )
        return docs


def _to_bytes(vec: list[float]) -> bytes:
    import struct

    return struct.pack(f"{len(vec)}f", *vec)


# 供 seed 脚本建索引使用
def create_index(client) -> None:
    try:
        client.ft(INDEX_NAME).info()
        return
    except Exception:  # noqa: BLE001
        pass
    client.ft(INDEX_NAME).create_index(
        fields=[
            sfield.TextField("title"),
            sfield.TextField("text"),
            sfield.TagField("doc_id"),
            sfield.TextField("params"),
            sfield.VectorField(
                "vec",
                "HNSW",
                {"TYPE": "FLOAT32", "DIM": DIM, "DISTANCE_METRIC": "COSINE"},
            ),
        ],
        definition=sfield.IndexDefinition(prefix=[PREFIX]),
    )
