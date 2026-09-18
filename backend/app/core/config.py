"""全局配置：一律从 backend/.env 读取（密钥只走 .env，不进系统环境变量）。"""
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录 = backend/app/core/config.py 向上三级
PROJECT_ROOT = Path(__file__).resolve().parents[3]

PUBLIC_DASHSCOPE = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- LLM ----
    llm_provider: str = "mock"  # mock | qwen | ollama
    qwen_model: str = "qwen-plus"
    # 兼容两种变量名：QWEN_API_KEY（推荐）/ DASHSCOPE_API_KEY（旧）
    qwen_api_key: str = Field(
        default="", validation_alias=AliasChoices("QWEN_API_KEY", "DASHSCOPE_API_KEY")
    )
    # 公网 DashScope 或专属推理端点（*.maas.aliyuncs.com）二选一，key 必须与端点匹配
    qwen_base_url: str = PUBLIC_DASHSCOPE
    # 单次 LLM 请求超时（秒）：专属端点结构化输出较慢，超时后走重试/降级而不是无限挂起
    qwen_timeout_sec: int = 90
    embedding_model: str = "text-embedding-v3"
    # embedding 独立端点：专属推理端点通常只含 chat 模型，向量模型走公网
    embedding_base_url: str = PUBLIC_DASHSCOPE

    # ---- Provider 切换 ----
    cv_provider: str = "mock"  # mock | yolo_http
    rag_provider: str = "mock"  # mock | redis_vector
    # mock 视觉场景选择：random=每次检测随机抽场景（演示用）；match=按工件号固定场景（评测回归用）
    cv_mock_mode: str = "random"

    # ---- 存储 ----
    pg_dsn: str = "postgresql+asyncpg://spray:spray_qc_2026@localhost:5432/spray_qc"
    redis_vector_dsn: str = "redis://localhost:6379/0"
    redis_state_dsn: str = "redis://localhost:6379/1"
    redis_state_ttl_sec: int = 86400
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_image_bucket: str = "inspection-images"
    minio_report_bucket: str = "reports"

    # ---- 安全 ----
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_min: int = 720

    # ---- 服务 ----
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- Mock 数据 ----
    mock_data_dir: str = str(PROJECT_ROOT / "mock_data")
    presign_expire_sec: int = 1800

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
