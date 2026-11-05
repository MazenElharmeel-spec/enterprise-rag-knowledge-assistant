from collections.abc import AsyncIterator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import decode_token
from backend.app.db.models import Membership, User
from backend.app.db.session import get_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_scoped_session(
    session: AsyncSession = Depends(get_session), token: str = Depends(oauth2_scheme)
) -> AsyncIterator[AsyncSession]:
    try:
        user_id, organization_id = decode_token(token)
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token") from exc
    groups_result = await session.execute(
        select(Membership.group_id).where(Membership.user_id == user_id)
    )
    groups = [str(group_id) for group_id in groups_result.scalars()]
    await session.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(user_id)}
    )
    await session.execute(
        text("SELECT set_config('app.organization_id', :org_id, true)"),
        {"org_id": str(organization_id)},
    )
    await session.execute(
        text("SELECT set_config('app.group_ids', :groups, true)"), {"groups": ",".join(groups)}
    )
    yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme), session: AsyncSession = Depends(get_session)
) -> User:
    try:
        user_id, organization_id = decode_token(token)
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token") from exc
    user = await session.scalar(
        select(User).where(
            User.id == user_id, User.organization_id == organization_id, User.is_active.is_(True)
        )
    )
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is inactive or no longer exists")
    return user


async def get_user_scoped_session(
    current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> AsyncIterator[AsyncSession]:
    group_ids = await session.scalars(
        select(Membership.group_id).where(Membership.user_id == current_user.id)
    )
    await session.execute(
        text("SELECT set_config('app.user_id', :v, true)"), {"v": str(current_user.id)}
    )
    await session.execute(
        text("SELECT set_config('app.organization_id', :v, true)"),
        {"v": str(current_user.organization_id)},
    )
    await session.execute(
        text("SELECT set_config('app.group_ids', :v, true)"), {"v": ",".join(map(str, group_ids))}
    )
    yield session
