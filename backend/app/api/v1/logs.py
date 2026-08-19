from datetime import date, timedelta
from decimal import Decimal
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from supabase import Client

from app.core.auth import get_current_user, get_current_user_client
from app.core.pagination import Pagination, pagination
from app.models.log import (
    DailyFoodLogCreate,
    DailyFoodLogResponse,
    DailyFoodLogUpdate,
    DailyMacros,
    MacroSummaryResponse,
    MacroTotals,
)
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


@router.get("/summary", response_model=MacroSummaryResponse)
async def get_macro_summary(
    period: Literal["week", "month"] = Query("week"),
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    """Average daily calories/macros over a rolling window (last 7 or 30
    days, including today).

    Averaged only over days that actually have at least one log entry -
    a day you forgot to log isn't "0 calories eaten," so counting it as
    zero in the average would silently drag it down and misrepresent
    what you actually eat, not just be imprecise about it.

    Joins food_logs -> custom_foods via PostgREST's FK-embed syntax (one
    query, RLS-scoped to the caller's own rows) rather than a raw SQL
    aggregate - the per-day summing/averaging happens in Python, same
    approach as the per-item meal estimate's total (Phase: dish-level
    logging).
    """
    days = 7 if period == "week" else 30
    start_date = date.today() - timedelta(days=days - 1)

    rows = (
        db.table("food_logs")
        .select("log_date, quantity, custom_foods(calories, protein_g, carbs_g, fat_g)")
        .eq("user_id", str(user.id))
        .gte("log_date", start_date.isoformat())
        .limit(5000)
        .execute()
        .data
    )

    by_day: dict[str, dict[str, Decimal]] = {}
    for row in rows:
        food = row.get("custom_foods")
        if not food:
            continue
        quantity = Decimal(str(row["quantity"]))
        bucket = by_day.setdefault(
            row["log_date"],
            {"calories": Decimal(0), "protein_g": Decimal(0), "carbs_g": Decimal(0), "fat_g": Decimal(0)},
        )
        bucket["calories"] += Decimal(str(food["calories"])) * quantity
        bucket["protein_g"] += Decimal(str(food["protein_g"])) * quantity
        bucket["carbs_g"] += Decimal(str(food["carbs_g"])) * quantity
        bucket["fat_g"] += Decimal(str(food["fat_g"])) * quantity

    daily = [
        DailyMacros(
            log_date=day,
            calories=int(totals["calories"]),
            protein_g=totals["protein_g"],
            carbs_g=totals["carbs_g"],
            fat_g=totals["fat_g"],
        )
        for day, totals in sorted(by_day.items())
    ]

    days_with_logs = len(daily)
    if days_with_logs == 0:
        average = MacroTotals(calories=0, protein_g=Decimal(0), carbs_g=Decimal(0), fat_g=Decimal(0))
    else:
        average = MacroTotals(
            calories=round(sum(d.calories for d in daily) / days_with_logs),
            protein_g=sum((d.protein_g for d in daily), Decimal(0)) / days_with_logs,
            carbs_g=sum((d.carbs_g for d in daily), Decimal(0)) / days_with_logs,
            fat_g=sum((d.fat_g for d in daily), Decimal(0)) / days_with_logs,
        )

    return MacroSummaryResponse(period=period, days_with_logs=days_with_logs, average=average, daily=daily)


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
