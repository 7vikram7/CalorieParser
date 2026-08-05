import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class UserCustomFoodBase(BaseModel):
    name: str
    serving_size_value: Decimal
    serving_size_unit: str  # e.g. 'g', 'ml', 'cup', 'scoop'
    calories: int
    protein_g: Decimal
    carbs_g: Decimal
    fat_g: Decimal


class UserCustomFoodCreate(UserCustomFoodBase):
    pass


class UserCustomFoodResponse(UserCustomFoodBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}
