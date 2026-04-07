"""
Team / Organisation multi-tenancy.

An organisation groups users together so they can share conversations,
API keys, and usage quotas. Each user can belong to multiple organisations
with different roles.

Endpoints:
  POST  /orgs                        — create an organisation
  GET   /orgs                        — list orgs the current user belongs to
  GET   /orgs/{id}                   — get org detail + members
  PATCH /orgs/{id}                   — update org name/settings (owner/admin only)
  DELETE /orgs/{id}                  — delete org (owner only)
  GET   /orgs/{id}/members           — list members with roles
  POST  /orgs/{id}/invite            — generate an invite token
  POST  /orgs/join/{invite_token}    — join via invite token
  DELETE /orgs/{id}/members/{uid}    — remove a member (admin/owner or self)

Member roles:
  owner  — full control, cannot be removed by others
  admin  — manage members and settings
  member — read/write within the org
"""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.db.session import get_db
from app.models.organization import Organization, OrganizationMember
from app.models.user import User
from app.schemas.common import SuccessResponse

router = APIRouter(prefix="/orgs", tags=["organizations"])


# ── Request / Response schemas ─────────────────────────────────────────────────

class OrgCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class OrgUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class OrgResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    invite_token: str | None
    invite_expires_at: datetime | None
    member_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class MemberResponse(BaseModel):
    user_id: UUID
    username: str
    email: str
    full_name: str | None
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class OrgDetailResponse(OrgResponse):
    members: list[MemberResponse] = []


# ── Helper ─────────────────────────────────────────────────────────────────────

async def _get_member_role(
    db: AsyncSession, org_id: UUID, user_id: UUID
) -> OrganizationMember | None:
    result = await db.execute(
        select(OrganizationMember)
        .where(OrganizationMember.organization_id == org_id)
        .where(OrganizationMember.user_id == user_id)
    )
    return result.scalar_one_or_none()


def _require_role(member: OrganizationMember | None, *roles: str) -> None:
    if not member or member.role not in roles:
        raise PermissionDeniedError(
            f"This action requires one of these roles: {', '.join(roles)}"
        )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("", response_model=OrgDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_org(
    data: OrgCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgDetailResponse:
    """Create a new organisation. The creator automatically becomes owner."""
    org = Organization(name=data.name, description=data.description)
    db.add(org)
    await db.flush()

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.id,
        role="owner",
    )
    db.add(membership)
    await db.commit()
    await db.refresh(org)

    return OrgDetailResponse(
        id=org.id,
        name=org.name,
        description=org.description,
        invite_token=org.invite_token,
        invite_expires_at=org.invite_expires_at,
        member_count=1,
        created_at=org.created_at,
        members=[
            MemberResponse(
                user_id=current_user.id,
                username=current_user.username,
                email=current_user.email,
                full_name=current_user.full_name,
                role="owner",
                joined_at=membership.joined_at,
            )
        ],
    )


@router.get("", response_model=list[OrgResponse])
async def list_my_orgs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrgResponse]:
    """List all organisations the current user belongs to."""
    from sqlalchemy import func
    result = await db.execute(
        select(
            Organization,
            func.count(OrganizationMember.user_id).label("member_count"),
        )
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == current_user.id)
        .group_by(Organization.id)
        .order_by(Organization.created_at.desc())
    )
    rows = result.all()
    return [
        OrgResponse(
            id=org.id,
            name=org.name,
            description=org.description,
            invite_token=None,  # don't expose token in list
            invite_expires_at=org.invite_expires_at,
            member_count=count,
            created_at=org.created_at,
        )
        for org, count in rows
    ]


@router.get("/{org_id}", response_model=OrgDetailResponse)
async def get_org(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgDetailResponse:
    """Get organisation details with member list."""
    membership = await _get_member_role(db, org_id, current_user.id)
    if not membership:
        raise NotFoundError("Organisation not found or you are not a member")

    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Organisation not found")

    members_result = await db.execute(
        select(OrganizationMember, User)
        .join(User, User.id == OrganizationMember.user_id)
        .where(OrganizationMember.organization_id == org_id)
        .order_by(OrganizationMember.joined_at)
    )
    members_rows = members_result.all()

    member_count = len(members_rows)
    # Only expose invite_token to owners/admins
    invite = org.invite_token if membership.role in ("owner", "admin") else None

    return OrgDetailResponse(
        id=org.id,
        name=org.name,
        description=org.description,
        invite_token=invite,
        invite_expires_at=org.invite_expires_at,
        member_count=member_count,
        created_at=org.created_at,
        members=[
            MemberResponse(
                user_id=u.id,
                username=u.username,
                email=u.email,
                full_name=u.full_name,
                role=m.role,
                joined_at=m.joined_at,
            )
            for m, u in members_rows
        ],
    )


@router.patch("/{org_id}", response_model=OrgResponse)
async def update_org(
    org_id: UUID,
    data: OrgUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgResponse:
    """Update org name or description. Requires admin or owner role."""
    membership = await _get_member_role(db, org_id, current_user.id)
    _require_role(membership, "owner", "admin")

    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Organisation not found")

    if data.name is not None:
        org.name = data.name
    if data.description is not None:
        org.description = data.description

    await db.commit()
    await db.refresh(org)

    count_result = await db.execute(
        select(OrganizationMember).where(OrganizationMember.organization_id == org_id)
    )
    member_count = len(count_result.scalars().all())

    return OrgResponse(
        id=org.id, name=org.name, description=org.description,
        invite_token=None, invite_expires_at=org.invite_expires_at,
        member_count=member_count, created_at=org.created_at,
    )


@router.delete("/{org_id}", response_model=SuccessResponse)
async def delete_org(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Delete an organisation. Owner only."""
    membership = await _get_member_role(db, org_id, current_user.id)
    _require_role(membership, "owner")

    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Organisation not found")

    await db.delete(org)
    await db.commit()
    return SuccessResponse(message="Organisation deleted")


@router.post("/{org_id}/invite", response_model=dict)
async def create_invite(
    org_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Generate a single-use invite token (valid 7 days).
    Calling again replaces the previous token.
    """
    membership = await _get_member_role(db, org_id, current_user.id)
    _require_role(membership, "owner", "admin")

    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Organisation not found")

    org.invite_token = secrets.token_urlsafe(24)
    org.invite_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.commit()

    return {
        "invite_token": org.invite_token,
        "expires_at": org.invite_expires_at.isoformat(),
    }


@router.post("/join/{invite_token}", response_model=SuccessResponse)
async def join_org(
    invite_token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """Join an organisation using a valid invite token."""
    result = await db.execute(
        select(Organization).where(Organization.invite_token == invite_token)
    )
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Invalid or expired invite token")
    if org.invite_expires_at and org.invite_expires_at < datetime.now(timezone.utc):
        raise NotFoundError("Invite token has expired")

    # Check not already a member
    existing = await _get_member_role(db, org.id, current_user.id)
    if existing:
        raise ConflictError("You are already a member of this organisation")

    membership = OrganizationMember(
        organization_id=org.id,
        user_id=current_user.id,
        role="member",
    )
    db.add(membership)
    await db.commit()

    return SuccessResponse(message=f"Joined organisation '{org.name}'")


@router.delete("/{org_id}/members/{user_id}", response_model=SuccessResponse)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    """
    Remove a member from the organisation.
    Allowed if: current user is owner/admin, OR current user is removing themselves.
    Cannot remove the owner.
    """
    caller_membership = await _get_member_role(db, org_id, current_user.id)
    if not caller_membership:
        raise NotFoundError("Organisation not found or you are not a member")

    target_membership = await _get_member_role(db, org_id, user_id)
    if not target_membership:
        raise NotFoundError("User is not a member of this organisation")

    # Self-removal is always allowed
    is_self = current_user.id == user_id
    is_admin_or_owner = caller_membership.role in ("owner", "admin")

    if not is_self and not is_admin_or_owner:
        raise PermissionDeniedError("Only admins and owners can remove other members")

    if target_membership.role == "owner" and not is_self:
        raise PermissionDeniedError("Cannot remove the organisation owner")

    await db.delete(target_membership)
    await db.commit()
    return SuccessResponse(message="Member removed")
