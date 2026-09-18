"""CV Provider 统一契约：Mock 与真实 YOLO 服务共同遵守（文档 6.2）。"""
from pydantic import BaseModel, Field


class ImageSize(BaseModel):
    width: int
    height: int


class DetectionMeasure(BaseModel):
    area_cm2: float | None = None
    max_length_mm: float | None = None
    delta_e: float | None = None  # 色差（color_deviation 专用）


class DetectionItem(BaseModel):
    id: int
    defect_type: str = Field(
        description="sagging|orange_peel|color_deviation|particle|pinhole|scratch"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    bbox_xyxy: list[int] = Field(min_length=4, max_length=4)
    measure: DetectionMeasure = Field(default_factory=DetectionMeasure)


class CVResult(BaseModel):
    """CVProvider.detect 的返回契约，LangGraph 节点只依赖此结构。"""

    model: str
    image_key: str
    image_size: ImageSize
    detections: list[DetectionItem] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


DEFECT_TYPES = {
    "sagging": "流挂",
    "orange_peel": "橘皮",
    "color_deviation": "色差",
    "particle": "颗粒",
    "pinhole": "针孔",
    "scratch": "划伤",
}


def defect_cn(defect_type: str) -> str:
    return DEFECT_TYPES.get(defect_type, defect_type)
