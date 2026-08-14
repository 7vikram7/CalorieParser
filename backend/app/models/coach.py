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
    # Populated only on routes that embed the counterpart's profile
    # (list_my_athletes embeds the athlete's, list_pending_invites embeds
    # the coach's) - None on routes that don't, e.g. invite_athlete's
    # response, since the frontend already knows what it just invited.
    athlete_email: Optional[str] = None
    athlete_name: Optional[str] = None
    coach_email: Optional[str] = None
    coach_name: Optional[str] = None

    model_config = {"from_attributes": True}
