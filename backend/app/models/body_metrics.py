import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class BodyMetricsBase(BaseModel):
    height_cm: Optional[Decimal] = None
    weight_kg: Optional[Decimal] = None
    bmr: Optional[int] = None
    activity_level: Optional[str] = None  # 'sedentary' | 'lightly_active' | 'moderately_active' | 'very_active' | 'extra_active'


class BodyMetricsCreate(BodyMetricsBase):
    pass


class BodyMetricsUpdate(BodyMetricsBase):
    pass


class BodyMetricsResponse(BodyMetricsBase):
    id: uuid.UUID
    user_id: uuid.UUID
    updated_at: datetime

    model_config = {"from_attributes": True}
