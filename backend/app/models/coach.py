import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr

CoachLinkStatus = Literal["pending", "active", "revoked"]


class CoachAthleteLinkInvite(BaseModel):
    """A coach invites an athlete by email. Backend resolves email -> user_id."""

    athlete_email: EmailStr


class CoachAthleteLinkRespond(BaseModel):
    """The athlete accepts or declines a pending invite."""

    status: Literal["active", "revoked"]


class CoachAthleteLinkResponse(BaseModel):
    id: uuid.UUID
    coach_id: uuid.UUID
    athlete_id: uuid.UUID
    status: CoachLinkStatus
    created_at: datetime
    responded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
