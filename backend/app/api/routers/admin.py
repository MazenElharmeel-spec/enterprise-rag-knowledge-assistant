from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user, get_user_scoped_session
from backend.app.db.models import Document, Group, Membership, User

router = APIRouter(prefix="/admin", tags=["admin"])


class GroupIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


def require_admin(user: User) -> None:
    if user.role != "admin":
        raise HTTPException(403, "Administrator access required")


@router.get("/overview")
async def overview(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_user_scoped_session)
) -> dict[str, int]:
    require_admin(user)
    users = await session.scalar(
        select(func.count()).select_from(User).where(User.organization_id == user.organization_id)
    )
    docs = await session.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.organization_id == user.organization_id, Document.is_retired.is_(False))
    )
    groups = await session.scalar(
        select(func.count()).select_from(Group).where(Group.organization_id == user.organization_id)
    )
    indexed = await session.scalar(
        select(func.count())
        .select_from(Document)
        .where(
            Document.organization_id == user.organization_id,
            Document.status == "indexed",
            Document.is_retired.is_(False),
        )
    )
    return {
        "users": users or 0,
        "documents": docs or 0,
        "groups": groups or 0,
        "indexed_documents": indexed or 0,
    }


@router.get("/users")
async def users(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_user_scoped_session)
) -> list[dict[str, str]]:
    require_admin(user)
    rows = await session.scalars(
        select(User).where(User.organization_id == user.organization_id).order_by(User.full_name)
    )
    return [
        {"id": str(row.id), "name": row.full_name, "email": row.email, "role": row.role}
        for row in rows
    ]


@router.get("/groups")
async def groups(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_user_scoped_session)
) -> list[dict[str, str | int]]:
    require_admin(user)
    rows = await session.scalars(
        select(Group).where(Group.organization_id == user.organization_id).order_by(Group.name)
    )
    result: list[dict[str, str | int]] = []
    for row in rows:
        count = await session.scalar(
            select(func.count()).select_from(Membership).where(Membership.group_id == row.id)
        )
        result.append({"id": str(row.id), "name": row.name, "members": int(count or 0)})
    return result


@router.post("/groups", status_code=201)
async def create_group(
    payload: GroupIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_user_scoped_session),
) -> dict[str, str]:
    require_admin(user)
    group = Group(organization_id=user.organization_id, name=payload.name.strip())
    session.add(group)
    await session.commit()
    return {"id": str(group.id), "name": group.name}
