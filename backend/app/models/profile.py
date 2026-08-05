import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class ProfileBase(BaseModel):
    display_name: Optional[str] = None


class ProfileUpdate(ProfileBase):
    pass


class ProfileResponse(ProfileBase):
    id: uuid.UUID
    email: EmailStr
    is_coach: bool
    created_at: datetime

    model_config = {"from_attributes": True}
