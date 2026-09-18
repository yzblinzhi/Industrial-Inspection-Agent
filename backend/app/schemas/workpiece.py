from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StandardIn(BaseModel):
    defect_type: str
    max_area_cm2: Decimal | None = None
    max_count: int | None = None
    max_dimension_mm: Decimal | None = None
    confidence_threshold: Decimal | None = Field(default=None, ge=0, le=1)
    extra_rules: dict = Field(default_factory=dict)


class StandardOut(StandardIn):
    id: int
    workpiece_id: int


class WorkpieceCreate(BaseModel):
    workpiece_no: str
    name: str
    material: str | None = None
    coating_spec: str | None = None
    description: str | None = None
    standards: list[StandardIn] = Field(default_factory=list)


class StandardUpsertRequest(BaseModel):
    standards: list[StandardIn]


class WorkpieceOut(BaseModel):
    id: int
    workpiece_no: str
    name: str
    material: str | None
    coating_spec: str | None
    description: str | None
    created_at: datetime
    standards: list[StandardOut] = Field(default_factory=list)
