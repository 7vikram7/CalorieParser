import uuid

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    """The authenticated identity, as decoded from the Supabase JWT.

    FastAPI never creates or updates this — Supabase Auth owns signup/login
    entirely from the Next.js frontend. Only carries what a JWT payload
    actually contains (`sub`, `email`); anything profile-related (display
    name, is_coach, when the profile row was created) lives in
    `ProfileResponse`, fetched separately.
    """

    id: uuid.UUID
    email: EmailStr

    model_config = {"from_attributes": True}
