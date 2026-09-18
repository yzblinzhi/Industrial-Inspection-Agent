"""API 冒烟：应用可创建、/health 可用（Checkpointer 自动降级路径也被触发）。"""
from fastapi.testclient import TestClient

from app.main import app


def test_health():
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["providers"]["cv"] in ("mock", "yolo_http")
        assert body["providers"]["llm"] in ("mock", "qwen", "ollama")


def test_protected_endpoint_requires_token():
    with TestClient(app) as client:
        resp = client.get("/api/v1/conversations")
        assert resp.status_code == 401
