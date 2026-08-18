from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class FoodEstimateRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)


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


class MealEstimateTotals(BaseModel):
    """Plain sum across a meal's items - computed in Python, never
    estimated by the LLM. Deliberately no name/serving/confidence: those
    only make sense per-dish, not for a sum.
    """

    calories: int
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal


class FoodEstimateResponse(BaseModel):
    description: str
    items: list[NutritionalEstimate]
    total: MealEstimateTotals
