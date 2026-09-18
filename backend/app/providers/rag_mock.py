"""RAG Mock：mock_data/knowledge/*.md 关键词倒排匹配。
front-matter 携带参数取值范围（params 为内联 JSON），供自检节点做区间校验。"""
import json
import logging
from pathlib import Path

from app.core.config import get_settings
from app.providers.base import RAGProvider

logger = logging.getLogger(__name__)


def _parse_front_matter(text: str) -> tuple[dict, str]:
    """解析 `---\\nkey: value\\n---\\n正文` 格式，返回 (元数据, 正文)。"""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict = {}
    for line in parts[1].strip().splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip(), value.strip()
        if key == "params":
            try:
                meta[key] = json.loads(value)
            except json.JSONDecodeError:
                meta[key] = {}
        else:
            meta[key] = value
    return meta, parts[2].strip()


class MockRAGProvider(RAGProvider):
    def __init__(self) -> None:
        self.dir = Path(get_settings().mock_data_dir) / "knowledge"
        self._cache: list[dict] | None = None

    def _load_docs(self) -> list[dict]:
        if self._cache is not None:
            return self._cache
        docs = []
        if self.dir.exists():
            for f in sorted(self.dir.glob("*.md")):
                meta, body = _parse_front_matter(f.read_text(encoding="utf-8"))
                docs.append(
                    {
                        "doc_id": meta.get("doc_id", f.stem),
                        "title": meta.get("title", f.stem),
                        "keywords": [
                            k.strip()
                            for k in meta.get("defect_keywords", "").split(",")
                            if k.strip()
                        ],
                        "text": body,
                        "params": meta.get("params", {}),
                    }
                )
        self._cache = docs
        return docs

    async def retrieve(self, query: str, top_k: int = 3) -> list[dict]:
        docs = self._load_docs()
        scored = []
        for d in docs:
            score = sum(1 for kw in d["keywords"] if kw and kw.lower() in query.lower())
            if score > 0:
                scored.append(
                    {
                        "doc_id": d["doc_id"],
                        "title": d["title"],
                        "text": d["text"],
                        "score": round(score / max(len(d["keywords"]), 1), 3),
                        "params": d["params"],
                    }
                )
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
