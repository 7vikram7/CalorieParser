from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends
from supabase import Client

from app.core.auth import get_current_user, get_current_user_client
from app.core.pagination import Pagination, pagination
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
    page: Pagination = Depends(pagination),
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    query = db.table("workouts").select("*").eq("user_id", str(user.id))
    if workout_date is not None:
        query = query.eq("workout_date", workout_date.isoformat())
    return query.order("workout_date", desc=True).range(*page.range()).execute().data


@router.delete("/workouts/{workout_id}", status_code=204)
async def delete_workout(
    workout_id: str,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    """Cascades to workout_sets via the FK's ON DELETE CASCADE - deleting a
    workout deletes every set (and PR flag) logged under it too.
    """
    db.table("workouts").delete().eq("id", workout_id).eq("user_id", str(user.id)).execute()


@router.get("/workouts/athlete/{athlete_id}", response_model=list[WorkoutResponse])
async def list_athlete_workouts(
    athlete_id: str,
    page: Pagination = Depends(pagination),
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
        .range(*page.range())
        .execute()
        .data
    )


@router.post("/workouts/{workout_id}/sets", response_model=WorkoutSetResponse)
async def add_set(
    workout_id: str,
    payload: WorkoutSetCreate,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    """RLS enforces the workout belongs to the caller — no ownership check
    needed here beyond scoping the insert to this workout_id.

    is_pr is computed here, never trusted from the client: a set counts as a
    PR if its weight_kg beats every weight_kg this user has ever logged for
    that exercise, across all of their workouts (not just this one).
    """
    body = payload.model_dump(mode="json")
    body["exercise_id"] = str(payload.exercise_id)

    is_pr = False
    if payload.weight_kg is not None:
        previous = (
            db.table("workout_sets")
            .select("weight_kg, workouts!inner(user_id)")
            .eq("exercise_id", str(payload.exercise_id))
            .eq("workouts.user_id", str(user.id))
            .execute()
        )
        previous_max = max(
            (Decimal(str(s["weight_kg"])) for s in previous.data if s["weight_kg"] is not None),
            default=None,
        )
        is_pr = previous_max is None or payload.weight_kg > previous_max

    result = (
        db.table("workout_sets")
        .insert({**body, "workout_id": workout_id, "is_pr": is_pr})
        .execute()
    )
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
