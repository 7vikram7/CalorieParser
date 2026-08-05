import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class DailyFoodLogBase(BaseModel):
    food_id: uuid.UUID
    log_date: date
    quantity: Decimal  # number of servings, e.g. 1.5
    meal_type: Optional[str] = None  # 'breakfast' | 'lunch' | 'dinner' | 'snack'


class DailyFoodLogCreate(DailyFoodLogBase):
    pass


class DailyFoodLogResponse(DailyFoodLogBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
