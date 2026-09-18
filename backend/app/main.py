"""FastAPI 入口：生命周期内构建 Checkpointer 与质检图（文档 12 / main）。"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import (
    admin,
    auth,
    chat,
    conversations,
    files,
    inspections,
    reviews,
    upload,
    workpieces,
)
from app.core.checkpointer import build_checkpointer
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.graph.builder import build_graph
from app.providers.factory import get_cv_provider, get_llm_provider, get_rag_provider
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    checkpointer = await build_checkpointer()
    app.state.graph = build_graph(checkpointer)
    app.state.agent = AgentService(app.state.graph)
    logger.info(
        "服务就绪 | CV=%s RAG=%s LLM=%s",
        settings.cv_provider, settings.rag_provider, settings.llm_provider,
    )
    yield
    from app.core.db import engine

    await engine.dispose()


settings = get_settings()
app = FastAPI(title="喷涂作业后工件质量检测与评估智能体", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "providers": {
            "cv": settings.cv_provider,
            "rag": settings.rag_provider,
            "llm": settings.llm_provider,
        },
    }


for r in (auth, chat, upload, conversations, inspections, workpieces, files, admin, reviews):
    app.include_router(r.router, prefix="/api/v1")
