from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.core.auth import get_current_user, get_current_user_client
from app.models.coach import (
    CoachAthleteLinkInvite,
    CoachAthleteLinkResponse,
    CoachAthleteLinkRespond,
)
from app.models.user import UserResponse

router = APIRouter(prefix="/coaches", tags=["coaches"])


@router.post("/invite", response_model=CoachAthleteLinkResponse, status_code=201)
async def invite_athlete(
    payload: CoachAthleteLinkInvite,
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    """The caller (a coach) invites an athlete by email. `profiles.email` is
    readable by any authenticated user (see RLS policy), so this is a plain
    lookup under the caller's own token — no service-role client needed.
    """
    athlete = db.table("profiles").select("id").eq("email", payload.athlete_email).execute()
    if not athlete.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that email")
    athlete_id = athlete.data[0]["id"]

    result = (
        db.table("coach_athlete_links")
        .insert({"coach_id": str(user.id), "athlete_id": athlete_id})
        .execute()
    )
    return result.data[0]


@router.get("/invites/pending", response_model=list[CoachAthleteLinkResponse])
async def list_pending_invites(
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    """Pending invites where the caller is the athlete being invited."""
    return (
        db.table("coach_athlete_links")
        .select("*")
        .eq("athlete_id", str(user.id))
        .eq("status", "pending")
        .execute()
        .data
    )


@router.patch("/links/{link_id}", response_model=CoachAthleteLinkResponse)
async def respond_to_invite(
    link_id: str,
    payload: CoachAthleteLinkRespond,
    db: Client = Depends(get_current_user_client),
):
    """The athlete accepts ('active') or declines ('revoked') a pending
    invite. RLS's "parties update own coach links" policy is what actually
    restricts this to the coach or athlete on the link.
    """
    result = (
        db.table("coach_athlete_links")
        .update({"status": payload.status, "responded_at": "now()"})
        .eq("id", link_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    return result.data[0]


@router.get("/athletes", response_model=list[CoachAthleteLinkResponse])
async def list_my_athletes(
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    """Active links where the caller is the coach."""
    return (
        db.table("coach_athlete_links")
        .select("*")
        .eq("coach_id", str(user.id))
        .eq("status", "active")
        .execute()
        .data
    )
