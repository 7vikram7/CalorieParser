from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class FoodEstimateRequest(BaseModel):
    description: str


class NutritionalEstimate(BaseModel):
    name: str
    serving_size_value: Decimal
    serving_size_unit: str
    calories: int
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal
    confidence: float  # 0.0-1.0 score returned by the AI layer
    notes: Optional[str] = None  # any caveats or assumptions made


class FoodEstimateResponse(BaseModel):
    description: str
    estimate: NutritionalEstimate
