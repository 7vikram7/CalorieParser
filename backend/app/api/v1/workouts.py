from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends
from supabase import Client

from app.core.auth import get_current_user, get_current_user_client
from app.models.user import UserResponse
from app.models.workout import (
    ExerciseCreate,
    ExerciseResponse,
    WorkoutCreate,
    WorkoutResponse,
    WorkoutSetCreate,
    WorkoutSetResponse,
)

router = APIRouter(tags=["workouts"])


@router.get("/exercises", response_model=list[ExerciseResponse])
async def list_exercises(db: Client = Depends(get_current_user_client)):
    """Shared catalog + any custom exercises visible to any signed-in user."""
    return db.table("exercises").select("*").order("name").execute().data


@router.post("/exercises", response_model=ExerciseResponse)
async def create_custom_exercise(
    payload: ExerciseCreate,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    body = {**payload.model_dump(), "is_custom": True, "created_by": str(user.id)}
    result = db.table("exercises").insert(body).execute()
    return result.data[0]


@router.post("/workouts", response_model=WorkoutResponse)
async def create_workout(
    payload: WorkoutCreate,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    body = payload.model_dump(mode="json")
    result = db.table("workouts").insert({**body, "user_id": str(user.id)}).execute()
    return result.data[0]


@router.get("/workouts", response_model=list[WorkoutResponse])
async def list_my_workouts(
    workout_date: Optional[date] = None,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    query = db.table("workouts").select("*").eq("user_id", str(user.id))
    if workout_date is not None:
        query = query.eq("workout_date", workout_date.isoformat())
    return query.order("workout_date", desc=True).execute().data


@router.get("/workouts/athlete/{athlete_id}", response_model=list[WorkoutResponse])
async def list_athlete_workouts(
    athlete_id: str,
    db: Client = Depends(get_current_user_client),
):
    """A coach reading an athlete's workouts — allowed only by the
    `is_active_coach_of` RLS policy, same pattern as logs.athlete_id.
    """
    return (
        db.table("workouts")
        .select("*")
        .eq("user_id", athlete_id)
        .order("workout_date", desc=True)
        .execute()
        .data
    )


@router.post("/workouts/{workout_id}/sets", response_model=WorkoutSetResponse)
async def add_set(
    workout_id: str,
    payload: WorkoutSetCreate,
    db: Client = Depends(get_current_user_client),
):
    """RLS enforces the workout belongs to the caller — no ownership check
    needed here beyond scoping the insert to this workout_id.
    """
    body = payload.model_dump(mode="json")
    body["exercise_id"] = str(payload.exercise_id)
    result = db.table("workout_sets").insert({**body, "workout_id": workout_id}).execute()
    return result.data[0]


@router.get("/workouts/{workout_id}/sets", response_model=list[WorkoutSetResponse])
async def list_sets(workout_id: str, db: Client = Depends(get_current_user_client)):
    return (
        db.table("workout_sets")
        .select("*")
        .eq("workout_id", workout_id)
        .order("set_number")
        .execute()
        .data
    )
