from datetime import datetime, timezone

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


def _flatten_athlete(row: dict) -> dict:
    """Pulls the embedded `athlete:profiles!athlete_id(...)` sub-object
    (from a `.select("*, athlete:profiles!athlete_id(...)")` query) up
    into the flat `athlete_email`/`athlete_name` fields
    CoachAthleteLinkResponse actually has - PostgREST returns embeds as
    nested objects, not flat columns.
    """
    athlete = row.pop("athlete", None) or {}
    row["athlete_email"] = athlete.get("email")
    row["athlete_name"] = athlete.get("display_name")
    return row


def _flatten_coach(row: dict) -> dict:
    coach = row.pop("coach", None) or {}
    row["coach_email"] = coach.get("email")
    row["coach_name"] = coach.get("display_name")
    return row


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
    athlete = db.table("profiles").select("id, email, display_name").eq("email", payload.athlete_email).execute()
    if not athlete.data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that email")
    athlete_id = athlete.data[0]["id"]

    if athlete_id == str(user.id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot invite yourself")

    existing = (
        db.table("coach_athlete_links")
        .select("id")
        .eq("coach_id", str(user.id))
        .eq("athlete_id", athlete_id)
        .execute()
    )
    if existing.data:
        raise HTTPException(status.HTTP_409_CONFLICT, "Invite already exists for this athlete")

    result = (
        db.table("coach_athlete_links")
        .insert({"coach_id": str(user.id), "athlete_id": athlete_id})
        .execute()
    )
    link = result.data[0]
    link["athlete_email"] = athlete.data[0]["email"]
    link["athlete_name"] = athlete.data[0]["display_name"]
    return link


@router.get("/invites/pending", response_model=list[CoachAthleteLinkResponse])
async def list_pending_invites(
    user: UserResponse = Depends(get_current_user),
    db: Client = Depends(get_current_user_client),
):
    """Pending invites where the caller is the athlete being invited. Embeds
    the inviting coach's profile (readable by any authenticated user - see
    `profiles`' RLS policy) so the frontend can show a name/email instead
    of a raw coach_id.
    """
    rows = (
        db.table("coach_athlete_links")
        .select("*, coach:profiles!coach_id(email,display_name)")
        .eq("athlete_id", str(user.id))
        .eq("status", "pending")
        .execute()
        .data
    )
    return [_flatten_coach(row) for row in rows]


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
        .update({"status": payload.status, "responded_at": datetime.now(timezone.utc).isoformat()})
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
    """Active links where the caller is the coach. Embeds the athlete's
    profile so the frontend can show a name/email instead of a raw
    athlete_id - the coach still never gets access to the athlete's actual
    food/workout data through this embed, just the same email/display_name
    any authenticated user can already look up.
    """
    rows = (
        db.table("coach_athlete_links")
        .select("*, athlete:profiles!athlete_id(email,display_name)")
        .eq("coach_id", str(user.id))
        .eq("status", "active")
        .execute()
        .data
    )
    return [_flatten_athlete(row) for row in rows]
