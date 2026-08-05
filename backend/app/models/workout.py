import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

ExerciseCategory = str  # 'strength' | 'cardio' | 'mobility' | 'other'


class ExerciseBase(BaseModel):
    name: str
    category: Optional[ExerciseCategory] = None
    equipment: Optional[str] = None
    primary_muscle: Optional[str] = None


class ExerciseCreate(ExerciseBase):
    pass


class ExerciseResponse(ExerciseBase):
    id: uuid.UUID
    is_custom: bool
    created_by: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkoutBase(BaseModel):
    workout_date: date
    name: Optional[str] = None
    notes: Optional[str] = None
    duration_minutes: Optional[int] = None


class WorkoutCreate(WorkoutBase):
    pass


class WorkoutResponse(WorkoutBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkoutSetBase(BaseModel):
    exercise_id: uuid.UUID
    set_number: int
    reps: Optional[int] = None
    weight_kg: Optional[Decimal] = None
    duration_seconds: Optional[int] = None
    distance_m: Optional[Decimal] = None
    rpe: Optional[Decimal] = None  # rate of perceived exertion, 0-10
    notes: Optional[str] = None


class WorkoutSetCreate(WorkoutSetBase):
    pass


class WorkoutSetResponse(WorkoutSetBase):
    id: uuid.UUID
    workout_id: uuid.UUID

    model_config = {"from_attributes": True}
