from pydantic import BaseModel, Field


class ChatStreamRequest(BaseModel):
    """POST /api/v1/chat/stream 请求体。session_id 缺省=新建会话。"""

    session_id: str | None = None
    message: str = Field(min_length=1)
    image_key: str | None = None  # MinIO object key（先经 /upload/image 上传）


class UploadResponse(BaseModel):
    image_key: str
    preview_url: str
