from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import get_current_user
from backend.app.api.schemas import LoginIn, RefreshIn, TokenOut, UserOut
from backend.app.core.config import get_settings
from backend.app.core.security import create_token, decode_token, verify_password
from backend.app.db.models import User
from backend.app.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


def token_response(user: User) -> TokenOut:
    settings = get_settings()
    return TokenOut(
        access_token=create_token(
            user.id,
            user.organization_id,
            "access",
            timedelta(minutes=settings.access_token_minutes),
        ),
        refresh_token=create_token(
            user.id, user.organization_id, "refresh", timedelta(days=settings.refresh_token_days)
        ),
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    user = await session.scalar(
        select(User).where(User.email == payload.email.lower(), User.is_active.is_(True))
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect")
    return token_response(user)


@router.post("/refresh", response_model=TokenOut)
async def refresh(payload: RefreshIn, session: AsyncSession = Depends(get_session)) -> TokenOut:
    try:
        user_id, organization_id = decode_token(payload.refresh_token, "refresh")
    except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token") from exc
    user = await session.scalar(
        select(User).where(
            User.id == user_id, User.organization_id == organization_id, User.is_active.is_(True)
        )
    )
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is inactive or no longer exists")
    return token_response(user)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)
