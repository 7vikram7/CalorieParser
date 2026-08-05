from fastapi import APIRouter, Depends
from supabase import Client

from app.core.auth import get_current_user, get_current_user_client
from app.models.estimation import FoodEstimateRequest, FoodEstimateResponse
from app.models.food import UserCustomFoodCreate, UserCustomFoodResponse
from app.models.user import UserResponse

router = APIRouter(prefix="/foods", tags=["foods"])


@router.post("/estimate", response_model=FoodEstimateResponse)
async def estimate_food(payload: FoodEstimateRequest):
    """Send a free-text food description to the AI layer and get back a
    structured nutritional estimate. Does not touch the database — the
    frontend calls POST /foods with the result if the user accepts it.
    """
    # TODO: call OpenAI (settings.OPENAI_API_KEY) with `payload.description`,
    # parse into NutritionalEstimate. No DB/auth dependency needed here.
    raise NotImplementedError


@router.post("", response_model=UserCustomFoodResponse)
async def create_custom_food(
    payload: UserCustomFoodCreate,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    result = (
        db.table("custom_foods")
        .insert({**payload.model_dump(), "user_id": str(user.id)})
        .execute()
    )
    return result.data[0]


@router.get("", response_model=list[UserCustomFoodResponse])
async def list_my_foods(
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    result = db.table("custom_foods").select("*").eq("user_id", str(user.id)).execute()
    return result.data
