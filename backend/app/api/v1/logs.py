from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.core.auth import get_current_user, get_current_user_client
from app.core.pagination import Pagination, pagination
from app.models.log import DailyFoodLogCreate, DailyFoodLogResponse, DailyFoodLogUpdate
from app.models.user import UserResponse

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post("", response_model=DailyFoodLogResponse)
async def create_log(
    payload: DailyFoodLogCreate,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    body = payload.model_dump(mode="json")
    body["food_id"] = str(payload.food_id)
    result = db.table("food_logs").insert({**body, "user_id": str(user.id)}).execute()
    return result.data[0]


@router.get("", response_model=list[DailyFoodLogResponse])
async def list_my_logs(
    log_date: Optional[date] = None,
    page: Pagination = Depends(pagination),
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    """Own logs for a given day, or all of them if `log_date` is omitted."""
    query = db.table("food_logs").select("*").eq("user_id", str(user.id))
    if log_date is not None:
        query = query.eq("log_date", log_date.isoformat())
    return query.range(*page.range()).execute().data


@router.get("/athlete/{athlete_id}", response_model=list[DailyFoodLogResponse])
async def list_athlete_logs(
    athlete_id: str,
    log_date: Optional[date] = None,
    page: Pagination = Depends(pagination),
    db: Client = Depends(get_current_user_client),
):
    """A coach reading an athlete's logs. No explicit coach check here —
    RLS's `is_active_coach_of` policy is what actually allows or denies
    this; an unauthorized caller just gets an empty result set back.
    """
    query = db.table("food_logs").select("*").eq("user_id", athlete_id)
    if log_date is not None:
        query = query.eq("log_date", log_date.isoformat())
    return query.range(*page.range()).execute().data


@router.patch("/{log_id}", response_model=DailyFoodLogResponse)
async def update_log(
    log_id: str,
    payload: DailyFoodLogUpdate,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    """Correct a logged meal's quantity/meal_type/date after the fact -
    e.g. "that was 2 servings, not 1". Doesn't touch food_id: to log a
    genuinely different food, delete this entry and log a new one.
    """
    result = (
        db.table("food_logs")
        .update(payload.model_dump(mode="json", exclude_unset=True))
        .eq("id", log_id)
        .eq("user_id", str(user.id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Log not found")
    return result.data[0]


@router.delete("/{log_id}", status_code=204)
async def delete_log(
    log_id: str,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    db.table("food_logs").delete().eq("id", log_id).eq("user_id", str(user.id)).execute()
