from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.core.auth import get_current_user, get_current_user_client
from app.models.body_metrics import BodyMetricsResponse, BodyMetricsUpdate
from app.models.profile import ProfileResponse, ProfileUpdate
from app.models.user import UserResponse

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileResponse)
async def get_my_profile(
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    """The signed-in caller's own profile row (auto-created on signup)."""
    result = db.table("profiles").select("*").eq("id", str(user.id)).single().execute()
    return result.data


@router.patch("/me", response_model=ProfileResponse)
async def update_my_profile(
    payload: ProfileUpdate,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    result = (
        db.table("profiles")
        .update(payload.model_dump(exclude_unset=True))
        .eq("id", str(user.id))
        .execute()
    )
    return result.data[0]


@router.get("/me/body-metrics", response_model=BodyMetricsResponse)
async def get_my_body_metrics(
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    """404s until the first PUT creates the row - body_metrics isn't
    auto-created on signup the way `profiles` is (see backend structure
    notes), so a brand-new user legitimately has none yet.
    """
    result = db.table("body_metrics").select("*").eq("user_id", str(user.id)).execute()
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No body metrics set yet")
    return result.data[0]


@router.put("/me/body-metrics", response_model=BodyMetricsResponse)
async def upsert_my_body_metrics(
    payload: BodyMetricsUpdate,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    result = (
        db.table("body_metrics")
        .upsert({**payload.model_dump(mode="json", exclude_unset=True), "user_id": str(user.id)})
        .execute()
    )
    return result.data[0]
