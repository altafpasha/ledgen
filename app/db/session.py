from typing import AsyncGenerator
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Async Engine for FastAPI
async_connect_args = {}
if settings.database_url.startswith("sqlite"):
    async_connect_args["check_same_thread"] = False

async_engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    connect_args=async_connect_args,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


from contextlib import asynccontextmanager
from sqlalchemy.pool import NullPool


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_task_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates an isolated async session with NullPool specifically for Celery worker tasks.
    Avoids 'Future attached to a different loop' errors across Celery task execution loops.
    """
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        echo=settings.debug,
        future=True,
        connect_args=async_connect_args,
    )
    task_session_maker = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with task_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
    await engine.dispose()



# Sync Engine for Celery Tasks & Migrations
sync_connect_args = {}
sync_url = settings.sync_database_url
if sync_url.startswith("sqlite"):
    sync_connect_args["check_same_thread"] = False

sync_engine = create_engine(
    sync_url,
    echo=settings.debug,
    future=True,
    connect_args=sync_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@contextmanager
def get_sync_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
