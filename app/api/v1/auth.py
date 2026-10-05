from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    RateLimiter,
    get_current_active_user,
    get_current_user,
    get_db,
    record_audit_log,
)
from app.core.config import settings
from app.core.exceptions import AuthenticationException, NotFoundException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_api_key,
    verify_password,
)
from app.db.models.user import APIKey, User
from app.schemas.auth import (
    APIKeyCreate,
    APIKeyRead,
    APIKeyResponse,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserRead,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User Login",
    description="Authenticates with email and password and returns JWT access & refresh tokens.",
    dependencies=[Depends(RateLimiter(requests_per_minute=10))],
)
async def login(
    req: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.email == req.email.lower().strip())
    res = await session.execute(stmt)
    user = res.scalars().first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise AuthenticationException("Invalid email or password.")

    if not user.is_active:
        raise AuthenticationException("Account is disabled.")

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    client_ip = request.client.host if request.client else None
    await record_audit_log(
        session=session,
        action="LOGIN_SUCCESS",
        resource_type="USER",
        resource_id=user.id,
        user_id=user.id,
        ip_address=client_ip,
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        refresh_token=refresh_token,
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Current User Profile",
    description="Retrieves the authenticated user's profile details.",
)
async def get_me(user: User = Depends(get_current_active_user)):
    return user


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh Access Token",
    description="Exchanges a valid refresh token for a newly minted access token.",
)
async def refresh_token(
    req: RefreshTokenRequest,
    session: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("type") != "refresh":
            raise AuthenticationException("Invalid token type.")
        user_id = payload.get("sub")
    except Exception:
        raise AuthenticationException("Invalid or expired refresh token.")

    stmt = select(User).where(User.id == user_id, User.is_active == True)
    res = await session.execute(stmt)
    user = res.scalars().first()
    if not user:
        raise AuthenticationException("User not found or inactive.")

    new_access_token = create_access_token(user.id)
    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post(
    "/api-keys",
    response_model=APIKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create API Key",
    description="Generates a new machine-to-machine API key. The raw key is returned only once.",
)
async def create_api_key_endpoint(
    data: APIKeyCreate,
    request: Request,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    raw_key, prefix, hashed_key = generate_api_key()
    expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_days) if data.expires_days else None

    api_key_record = APIKey(
        user_id=user.id,
        name=data.name,
        key_prefix=prefix,
        hashed_key=hashed_key,
        is_active=True,
        expires_at=expires_at,
    )
    session.add(api_key_record)
    await session.commit()
    await session.refresh(api_key_record)

    await record_audit_log(
        session=session,
        action="API_KEY_CREATED",
        resource_type="API_KEY",
        resource_id=api_key_record.id,
        user_id=user.id,
        details={"name": data.name, "key_prefix": prefix},
        ip_address=request.client.host if request.client else None,
    )

    return APIKeyResponse(
        id=api_key_record.id,
        name=api_key_record.name,
        key_prefix=prefix,
        api_key=raw_key,
        created_at=api_key_record.created_at,
        expires_at=expires_at,
    )


@router.get(
    "/api-keys",
    response_model=List[APIKeyRead],
    summary="List API Keys",
    description="Lists all API keys generated by the current user (only prefixes shown).",
)
async def list_api_keys_endpoint(
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(APIKey).where(APIKey.user_id == user.id).order_by(APIKey.created_at.desc())
    res = await session.execute(stmt)
    return list(res.scalars().all())


@router.delete(
    "/api-keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API Key",
    description="Revokes an existing API key immediately.",
)
async def revoke_api_key_endpoint(
    key_id: str,
    user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id)
    res = await session.execute(stmt)
    key_obj = res.scalars().first()
    if not key_obj:
        raise NotFoundException("APIKey", key_id)

    await session.delete(key_obj)
    await session.commit()
