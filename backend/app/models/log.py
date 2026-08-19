import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel

MealType = Literal["breakfast", "lunch", "dinner", "snack"]


class DailyFoodLogBase(BaseModel):
    food_id: uuid.UUID
    log_date: date
    quantity: Decimal  # number of servings, e.g. 1.5
    meal_type: Optional[MealType] = None


class DailyFoodLogCreate(DailyFoodLogBase):
    pass


class DailyFoodLogUpdate(BaseModel):
    quantity: Optional[Decimal] = None
    meal_type: Optional[MealType] = None
    log_date: Optional[date] = None


class DailyFoodLogResponse(DailyFoodLogBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class MacroTotals(BaseModel):
    calories: int
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal


class DailyMacros(MacroTotals):
    log_date: date


class MacroSummaryResponse(BaseModel):
    period: Literal["week", "month"]
    days_with_logs: int
    average: MacroTotals
    daily: list[DailyMacros]
