import hashlib
import time
import uuid
from typing import AsyncGenerator, Optional, Tuple, Union
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthenticationException, PermissionDeniedException, RateLimitException
from app.core.security import decode_token, hash_api_key
from app.db.models.user import User, APIKey, AuditLog
from app.db.session import get_async_session

security_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    session: AsyncSession = Depends(get_db),
) -> User:
    if not credentials or not credentials.credentials:
        raise AuthenticationException("Missing Bearer authorization token.")

    token = credentials.credentials

    # Check if token is an API key (prefix lgk_live_)
    if token.startswith("lgk_live_"):
        hashed = hash_api_key(token)
        stmt = select(APIKey).where(APIKey.hashed_key == hashed, APIKey.is_active == True)
        res = await session.execute(stmt)
        api_key = res.scalars().first()
        if not api_key:
            raise AuthenticationException("Invalid or inactive API key.")

        user_stmt = select(User).where(User.id == api_key.user_id, User.is_active == True)
        u_res = await session.execute(user_stmt)
        user = u_res.scalars().first()
        if not user:
            raise AuthenticationException("Associated user account is disabled.")
        return user

    # JWT Token verification
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if not user_id or token_type != "access":
            raise AuthenticationException("Invalid token type.")
    except Exception as e:
        raise AuthenticationException("Signature verification failed or token expired.")

    stmt = select(User).where(User.id == user_id)
    res = await session.execute(stmt)
    user = res.scalars().first()
    if not user:
        raise AuthenticationException("User not found.")
    if not user.is_active:
        raise PermissionDeniedException("User account is inactive.")

    return user


async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise PermissionDeniedException("Inactive user.")
    return user


async def get_current_superuser(user: User = Depends(get_current_user)) -> User:
    if not user.is_superuser:
        raise PermissionDeniedException("Administrative privileges required.")
    return user


# In-memory sliding window rate limiter fallback
_rate_limit_cache: dict = {}


class RateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute

    async def __call__(self, request: Request):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        minute_ago = now - 60

        # Try Redis if available
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url, decode_responses=True)
            key = f"rate_limit:{client_ip}:{request.url.path}"
            current = await r.incr(key)
            if current == 1:
                await r.expire(key, 60)
            if current > self.requests_per_minute:
                raise RateLimitException("Too many requests from this IP. Please slow down.")
            return
        except (RateLimitException,):
            raise
        except Exception:
            # Fallback to in-memory sliding window
            timestamps = _rate_limit_cache.get(client_ip, [])
            timestamps = [t for t in timestamps if t > minute_ago]
            if len(timestamps) >= self.requests_per_minute:
                raise RateLimitException("Rate limit reached. Please wait before making further calls.")
            timestamps.append(now)
            _rate_limit_cache[client_ip] = timestamps


async def record_audit_log(
    session: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    user_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
):
    from datetime import datetime, timezone
    log = AuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        details=details,
        ip_address=ip_address,
        created_at=datetime.now(timezone.utc),
    )
    session.add(log)
    await session.commit()
