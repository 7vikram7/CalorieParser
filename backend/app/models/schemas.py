# ---------------------------------------------------------------------------
# Backward-compatible re-exports.
# All models live in domain-specific files:
#   user.py | profile.py | body_metrics.py | coach.py | food.py | log.py
#   | workout.py | estimation.py
#
# Import directly from those files in new code. This file just re-exports
# everything so `from app.models.schemas import X` keeps working.
# ---------------------------------------------------------------------------

from app.models.body_metrics import (
    BodyMetricsBase,
    BodyMetricsCreate,
    BodyMetricsResponse,
    BodyMetricsUpdate,
)
from app.models.coach import (
    CoachAthleteLinkInvite,
    CoachAthleteLinkResponse,
    CoachAthleteLinkRespond,
    CoachLinkStatus,
)
from app.models.estimation import (
    FoodEstimateRequest,
    FoodEstimateResponse,
    NutritionalEstimate,
)
from app.models.food import UserCustomFoodBase, UserCustomFoodCreate, UserCustomFoodResponse
from app.models.log import DailyFoodLogBase, DailyFoodLogCreate, DailyFoodLogResponse
from app.models.profile import ProfileBase, ProfileResponse, ProfileUpdate
from app.models.user import UserResponse
from app.models.workout import (
    ExerciseBase,
    ExerciseCreate,
    ExerciseResponse,
    WorkoutBase,
    WorkoutCreate,
    WorkoutResponse,
    WorkoutSetBase,
    WorkoutSetCreate,
    WorkoutSetResponse,
)

__all__ = [
    "UserResponse",
    "ProfileBase", "ProfileUpdate", "ProfileResponse",
    "BodyMetricsBase", "BodyMetricsCreate", "BodyMetricsUpdate", "BodyMetricsResponse",
    "CoachLinkStatus", "CoachAthleteLinkInvite", "CoachAthleteLinkRespond", "CoachAthleteLinkResponse",
    "UserCustomFoodBase", "UserCustomFoodCreate", "UserCustomFoodResponse",
    "DailyFoodLogBase", "DailyFoodLogCreate", "DailyFoodLogResponse",
    "ExerciseBase", "ExerciseCreate", "ExerciseResponse",
    "WorkoutBase", "WorkoutCreate", "WorkoutResponse",
    "WorkoutSetBase", "WorkoutSetCreate", "WorkoutSetResponse",
    "FoodEstimateRequest", "NutritionalEstimate", "FoodEstimateResponse",
]
