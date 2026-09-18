"""Provider 连通性诊断（密钥不回显）。
用法（backend 目录）：uv run python scripts/check_providers.py
"""
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


async def main() -> None:
    from app.core.config import get_settings

    s = get_settings()
    print(f"当前配置: LLM_PROVIDER={s.llm_provider} | CV_PROVIDER={s.cv_provider} | RAG_PROVIDER={s.rag_provider}")
    key = s.qwen_api_key
    print(f"QWEN_API_KEY: {(key[:5] + '****' + key[-4:]) if len(key or '') > 12 else '(未填写或为占位符!)'}")
    print(f"QWEN_BASE_URL: {s.qwen_base_url}")

    if s.llm_provider == "mock":
        print("\n⚠️ 当前 LLM_PROVIDER=mock：所有 LLM 调用都是本地 Mock，不会请求通义千问。")
        print("   启用 qwen：编辑 backend/.env → LLM_PROVIDER=qwen 并填入真实 key，然后重启服务后重新运行本脚本。")
        return

    from langchain_core.messages import HumanMessage

    from app.providers.llm_qwen import QwenLLMProvider
    from app.schemas.intent import IntentParse

    p = QwenLLMProvider()
    print("\n[测试1] 普通对话（连通性）...")
    try:
        r = await p.chat([HumanMessage(content="只回复两个字母: OK")])
        print("  ✅ 成功:", str(r.content)[:60])
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 失败: {type(exc).__name__}: {str(exc)[:300]}")
        return

    print("\n[测试2] 结构化输出（意图解析，应用同款调用）...")
    try:
        res = await p.chat([HumanMessage(content="检测立柱 CL-ZH02-B，批次 B2026-09-01")], IntentParse)
        print("  ✅ 成功:", res.model_dump())
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 失败: {type(exc).__name__}: {str(exc)[:300]}")

    print("\n[测试3] Embedding（RAG 向量检索用）...")
    try:
        vec = await p.embed(["流挂缺陷工艺处置"])
        print(f"  ✅ 成功: {len(vec[0])} 维")
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 失败: {type(exc).__name__}: {str(exc)[:300]}")


if __name__ == "__main__":
    asyncio.run(main())
